# 05 — Arquitetura unificada

## Diagrama de componentes (proposto)

```
┌───────────────────────────────────────────────────────────────────┐
│  Hermes Agent (processo Python do usuário)                        │
│                                                                     │
│   hermes model  →  seleciona provider "claude-cli"                │
│         │                                                          │
│         ▼                                                          │
│   providers.get_provider_profile("claude-cli")                    │
│         │                                                          │
│         ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  $HERMES_HOME/plugins/model-providers/claude-cli/  (symlink) │  │
│  │       → aponta para plugin/claude_cli/ deste repositório     │  │
│  │                                                                │
│  │  ClaudeCLIProviderProfile(ProviderProfile)                   │  │
│  │    auth_type = "external_process"                            │  │
│  │    create_client() → ClaudeCLIClient(**kwargs)                │  │
│  │                                                                │
│  │  ClaudeCLIClient                                              │  │
│  │    .chat.completions.create(model, messages, stream, ...)    │  │
│  │      │                                                        │  │
│  │      ├─ protocol.py   → traduz messages OpenAI ⇄ prompt/flags│  │
│  │      ├─ session.py    → (v2) mapeia sessão Hermes ⇄ session-id│ │
│  │      └─ process.py    → subprocess.Popen(["claude", ...])    │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────────┘
                            │ stdio (argv + stdin/stdout, sem rede)
                            ▼
                    `claude` CLI (binário da Anthropic)
                            │ OAuth (~/.claude/.credentials.json)
                            ▼
                 Assinatura Claude Max (base plan allowance)
```

Comparar com a arquitetura original (2 repositórios): ver diagrama equivalente em [01](./01-analise-claude-bridge.md) — lá existia um salto de rede (`HTTP :9180`) e um processo systemd adicional que desaparecem aqui.

## Layout de módulos proposto (dentro deste repositório)

```
plugin/
└── claude_cli/                     # pacote Python, plugin do Hermes
    ├── plugin.yaml                 # manifesto (name, kind: model-provider, version, description, author)
    ├── __init__.py                 # registra ClaudeCLIProviderProfile via register_provider()
    ├── client.py                   # ClaudeCLIClient — implementa create_client()
    ├── protocol.py                 # tradução de mensagens OpenAI ⇄ prompt/flags do CLI
    ├── process.py                  # spawn/gestão do subprocesso `claude`, parsing de stream-json
    ├── config.py                   # leitura de variáveis de ambiente (ver docs/07)
    └── models.py                   # catálogo estático de aliases/modelos suportados
```

Cada módulo tem uma responsabilidade única (alinhado à regra "many small files > few large files"): `client.py` não sabe como formatar prompts, `protocol.py` não sabe invocar subprocesso, `process.py` não sabe nada sobre o formato OpenAI.

## Responsabilidades por módulo

### `__init__.py`
Equivalente ao `__init__.py` do repositório original, mas com `auth_type="external_process"` em vez de `env_vars` fake e `base_url` HTTP:

```python
class ClaudeCLIProviderProfile(ProviderProfile):
    def create_client(self, **client_kwargs):
        from .client import ClaudeCLIClient
        return ClaudeCLIClient(**client_kwargs)

claude_cli = ClaudeCLIProviderProfile(
    name="claude-cli",
    aliases=("claude", "claude-code", "claude-max", "claude-subscription"),
    display_name="Claude CLI (Max subscription)",
    auth_type="external_process",
    base_url="process://claude-cli",       # URL simbólica, nunca usada para rede
    process_command="claude",
    process_command_env_vars=("CLAUDE_CLI_BIN",),
    fallback_models=("sonnet", "opus", "haiku", "claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"),
    default_aux_model="haiku",
    supports_model_listing=False,           # não há endpoint /models — usa fallback_models
)
register_provider(claude_cli)
```

### `client.py` — `ClaudeCLIClient`
Espelha a superfície mínima do `CopilotACPClient` (ver [03](./03-modelo-de-provider-do-hermes.md)):
- `.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create_chat_completion))`
- `HERMES_SKIP_TRANSPORT_WRAP = True` (evita reencapsulamento pela camada HTTP genérica do Hermes)
- `_create_chat_completion(model, messages, stream, tools, ...)` decide entre subprocesso "one-shot" (v1) ou sessão resumível (v2, ver abaixo).

### `protocol.py`
Reimplementa (em Python, corrigindo os bugs achados em [01](./01-analise-claude-bridge.md)) a lógica de `flattenMessages`/`stringifyContent`/`mapStopReason` do `claude-bridge` original — mas alimentando de fato `--output-format json` ou `stream-json`, para que custo e uso de tokens **realmente** venham do CLI em vez de ficarem zerados.

### `process.py`
Gerencia o `subprocess.run`, incluindo:
- Modo `json` (uma chamada, resposta completa) — implementado na Fase 1 (`build_args`/`run_once`), com parsing real do JSON de saída verificado empiricamente contra o CLI de verdade.
- Timeout por chamada (o `claude-bridge` original usa 5 minutos fixos — mantido como default configurável).
- Ambiente do subprocesso: nunca herdar variáveis sensíveis do processo pai além do necessário (mesma preocupação que `hermes_subprocess_env()` resolve no `copilot_acp_client.py` de referência) — **ainda não implementado**, ver [10-roadmap.md](./10-roadmap.md) Fase 3.

> **Nota (pós-Fase 1):** o modo `stream-json`/`--include-partial-messages` descrito abaixo em "v2" **não** foi implementado como um parser incremental dedicado. Ver a seção "Fase 2" em [10-roadmap.md](./10-roadmap.md) para o porquê — o próprio cliente de referência do Hermes (`copilot_acp_client.py`) também não faz streaming token-a-token real para um provider de subprocesso; `client.py` monta a resposta completa e a expõe como um "stream" de um único chunk quando `stream=True`.

## Duas fases de invocação (v1 vs v2)

### v1 — paridade funcional, sem estado entre turnos
Cada chamada de `.create()`:
1. Achata `messages` num prompt único (system prompt via `--append-system-prompt`, transcript anterior + última mensagem do usuário).
2. Roda `claude -p --output-format json --model <alias> [flags de permissão]`.
3. Faz parse do JSON de saída real (`result`, `stop_reason`, `session_id`, `total_cost_usd`, `usage.{input,output}_tokens`) — **isso já corrige o bug do bridge original**, que nunca fazia esse parse.

### v2 — sessão contínua (otimização, não obrigatória para paridade)
Usa `--session-id <uuid>` na primeira chamada de uma conversa Hermes e `--resume <uuid>` nas seguintes, evitando reenviar o histórico inteiro a cada turno. Requer mapear `id da conversa/sessão do Hermes` → `session_id do claude CLI`, com uma política de expiração. Ver [10-roadmap.md](./10-roadmap.md) — não faz parte do escopo inicial porque adiciona estado que precisa ser testado com cuidado (o que acontece se a sessão do `claude` expirar, for compactada, etc.).

## Por que não existe mais `scripts/reload.sh`/systemd

Não há processo de longa duração para reiniciar. O "processo" agora é o subprocesso `claude`, criado e destruído a cada chamada (ou por sessão, em v2), dentro do ciclo de vida do próprio Hermes. Isso elimina uma classe inteira de problemas operacionais (processo zumbi, porta ocupada, reinício após crash) que o `claude-bridge` original precisava resolver com `scripts/reload.sh` (kill → build → start → poll health).

## Instalação (visão de alto nível, detalhes em roadmap)

Diferente do original (clonar 2 repos + `go build` + systemd), a instalação vira:

1. Clonar/ter este repositório disponível localmente.
2. Symlink de `plugin/claude_cli/` → `$HERMES_HOME/plugins/model-providers/claude-cli` (igual ao mecanismo original, só que sem repositório separado para o "bridge").
3. Nenhum build, nenhum binário adicional, nenhuma unit systemd.

Distribuição via `pip` + entry point (`hermes_agent.plugins`) fica registrada como evolução opcional em [10](./10-roadmap.md).
