# 03 — Como o Hermes Agent realmente trata providers

Fonte: código-fonte real de [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) (`providers/base.py`, `providers/__init__.py`, `plugins/model-providers/copilot-acp/`, `agent/copilot_acp_client.py`, `website/docs/developer-guide/adding-providers.md`) — **não** documentação de terceiros. Esta é a peça de análise que os dois repositórios originais não tinham (ou não aplicaram).

## Descoberta de plugins

`providers/__init__.py::_discover_providers()` escaneia, na primeira chamada a `get_provider_profile()` ou `list_providers()`:

1. `plugins/model-providers/<nome>/` — bundled no próprio Hermes Agent.
2. `$HERMES_HOME/plugins/model-providers/<nome>/` — plugins do usuário (**é aqui que nosso plugin será instalado**, exatamente como o `claude-cli` original fazia).
3. (opcional, opt-in) pacotes `pip` que declaram um entry point `hermes_agent.plugins`.

Cada diretório precisa de `__init__.py` (chama `register_provider(profile)` no nível de módulo) + `plugin.yaml` (manifesto: `name`, `kind: model-provider`, `version`, `description`, `author`). Plugins de usuário sobrescrevem bundled do mesmo nome (last-writer-wins).

## A abstração central: `ProviderProfile` (dataclass, `providers/base.py`)

Campos relevantes para esta análise:

- `api_mode: str = "chat_completions"` — como o transporte formata o request. Valores possíveis no código-fonte: `chat_completions` (a maioria dos providers, incl. o `claude-cli` original), `anthropic_messages` (o provider `anthropic` nativo do Hermes), `codex_responses` (OpenAI Codex, xAI Grok, Meta/Muse Spark, Ramp Router).
- `auth_type: str = "api_key"` — outros valores: `oauth_device_code`, `oauth_external`, `copilot`, `aws_sdk`, **`external_process`**.
- `base_url: str` — obrigatório para o caminho HTTP padrão.
- **Campos específicos de `auth_type="external_process"`**: `process_command`, `process_args`, `process_command_env_vars`, `process_args_env_var` — "An agent CLI driven over stdio (ACP) rather than an HTTP endpoint." (comentário literal do código-fonte).
- **`create_client(self, **client_kwargs) -> Any | None`** — hook que, por padrão, retorna `None` (o core constrói o cliente `openai.OpenAI` padrão apontando para `base_url`). Uma subclasse pode sobrescrever e devolver **qualquer objeto** que implemente a interface mínima que o restante do Hermes espera (`.chat.completions.create(...)`), incluindo um objeto que não faz nenhuma chamada de rede. Docstring literal:

  > "This is the hook that lets a provider ship *outside* this tree: with it, a profile registered from `~/.hermes/plugins/model-providers/` or a pip entry point can supply its own transport without any core edit. See `plugins/model-providers/copilot-acp/` for the in-tree example."

Ou seja: **o próprio Hermes Agent documenta, no código-fonte, que este é o mecanismo certo para o nosso caso de uso.**

## Prova de conceito já existente em produção: `copilot-acp`

`plugins/model-providers/copilot-acp/__init__.py` (bundled, mantido pela Nous Research):

```python
class CopilotACPProfile(ProviderProfile):
    def create_client(self, **client_kwargs):
        from agent.copilot_acp_client import CopilotACPClient
        return CopilotACPClient(**client_kwargs)

copilot_acp = CopilotACPProfile(
    name="copilot-acp",
    api_mode="chat_completions",       # o transporte trata como chat_completions
    base_url="acp://copilot",          # URL simbólica, nunca é usada para HTTP de fato
    auth_type="external_process",
    process_command="copilot",
    process_args=("--acp", "--stdio"),
    process_command_env_vars=("HERMES_COPILOT_ACP_COMMAND", "COPILOT_CLI_PATH"),
    process_args_env_var="HERMES_COPILOT_ACP_ARGS",
)
register_provider(copilot_acp)
```

`agent/copilot_acp_client.py` (476 linhas) implementa `CopilotACPClient`, uma classe que:

- Expõe `.chat.completions.create(...)` (via `SimpleNamespace`) — a mesma superfície que o SDK `openai` real exporia, então o resto do Hermes (`run_agent.py`) não precisa saber que não é HTTP.
- Internamente, faz `subprocess.Popen([...], stdin=PIPE, stdout=PIPE, stderr=PIPE)` do binário `copilot --acp --stdio` e conversa **JSON-RPC 2.0 sobre stdio** (protocolo ACP — Agent Client Protocol) diretamente, em threads próprias para ler stdout/stderr sem bloquear.
- Declara `HERMES_SKIP_TRANSPORT_WRAP = True` e `HERMES_SKIP_ASYNC_WRAP = True` — sinalizando ao core que este cliente já é "completo" e não deve ser re-envelopado pela camada de transporte HTTP genérica.
- Implementa timeouts, um "probe" de compatibilidade (`_acp_supported`) para falhar rápido se o binário não suportar o protocolo, tratamento de permissões de arquivo (`_ensure_path_within_cwd`, nega paths fora do `cwd` da sessão), e redação de conteúdo sensível (`redact_sensitive_text`) antes de devolver conteúdo de arquivos lidos pela sessão ACP.

**Este é o padrão de referência para a nova arquitetura** — não porque o `claude` CLI suporte o mesmo protocolo ACP (não suporta, ver [06](./06-referencia-cli-claude.md)), mas porque a **classe de solução** (`create_client()` + `auth_type="external_process"` + uma classe de cliente que fala com um subprocesso via stdio) é exatamente o buraco que o `claude-bridge` (HTTP) tentou preencher de um jeito mais pesado e menos seguro.

## Distribuição alternativa: entry point `pip`

`providers/__init__.py::_discover_entry_point_providers()` também suporta plugins distribuídos como pacote `pip` normal, via:

```toml
[project.entry-points."hermes_agent.plugins"]
claude-cli = "hermes_claude_cli:register"
```

Com uma ressalva importante: **é opt-in** — só carrega entry points cujo nome está na lista `plugins.enabled` da configuração do Hermes. É uma opção de distribuição mais "profissional" (versionamento via `pip`, sem symlink manual), mas exige que o usuário habilite explicitamente. Ver decisão de escopo em [10-roadmap.md](./10-roadmap.md) — v1 usa o caminho de diretório (igual ao original, sem fricção adicional), pip entry point fica como evolução futura opcional.

## O que isso implica para o "protocolo de wire"

O Hermes armazena histórico de conversa internamente no formato **OpenAI chat-completions** (mensagens com `role`/`content`, `tool_calls` com `function.arguments` stringificado, mensagens `role: "tool"`). Isso é verdade **independente do transporte** — mesmo o `CopilotACPClient`, que não fala HTTP, recebe `messages` no formato OpenAI e faz a tradução internamente para o protocolo nativo do backend. Ou seja, mesmo removendo o servidor HTTP, **ainda precisamos de uma camada de tradução de mensagens** — só que ela vive dentro do processo do Hermes, como código Python puro, e não como servidor de rede separado.
