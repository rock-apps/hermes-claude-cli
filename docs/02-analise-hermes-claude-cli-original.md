# 02 — Análise: `niski84/hermes-claude-cli` (repositório original de terceiro)

Repositório: https://github.com/niski84/hermes-claude-cli (Python, MIT, 2 commits).

> Nota: este é o repositório de **terceiro** que deu origem ao nome do projeto atual. Não confundir com este repositório (`rock-apps/hermes-claude-cli`), que está sendo reconstruído do zero a partir da análise aqui documentada.

## Estrutura (100% do conteúdo, é um repo minúsculo)

```
hermes-claude-cli/
├── plugin/claude-cli/
│   ├── plugin.yaml        # manifesto do plugin Hermes
│   └── __init__.py        # ~85 linhas — registra um ProviderProfile
├── scripts/install.sh     # ~140 linhas — instalador
├── LICENSE (MIT)
└── README.md
```

## O que o `__init__.py` faz de fato

```python
from providers import register_provider
from providers.base import ProviderProfile

claude_cli = ProviderProfile(
    name="claude-cli",
    aliases=("claude", "claude-code", "claude-max", "claude-subscription"),
    env_vars=("CLAUDE_BRIDGE_URL",),
    display_name="Claude CLI (Max subscription)",
    base_url=BASE_URL,  # http://localhost:9180/v1 por padrão
    fallback_models=("sonnet", "opus", "haiku", "claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"),
    default_aux_model="haiku",
    default_headers={"X-Title": "Hermes Agent (via Claude CLI bridge)"},
)
register_provider(claude_cli)
```

Isso usa exatamente o **"fast path" documentado oficialmente** pelo Hermes Agent para providers simples compatíveis com OpenAI (ver [03](./03-modelo-de-provider-do-hermes.md)): nenhuma classe customizada, nenhum override de hook, `api_mode` implícito (`chat_completions`, o default da dataclass `ProviderProfile`). O comentário no próprio código admite o truque: `env_vars=("CLAUDE_BRIDGE_URL",)` existe só porque "Hermes' model picker only shows providers with at least one env var present" — não é uma credencial de verdade, é um hack para o provider aparecer no menu `hermes model`.

**Conclusão relevante para a arquitetura**: este plugin, por si só, é **trivial e correto** dentro do modelo mental que ele assume (provider = endpoint HTTP compatível com OpenAI). O problema não está aqui — está na dependência total do `claude-bridge` rodando como processo HTTP externo. Ou seja, **90% do valor arquitetural deste repositório se resume a 6 linhas de configuração de um `ProviderProfile`**; o resto (`install.sh`) é orquestração de infraestrutura em torno do bridge.

## O que o `scripts/install.sh` faz

1. Checa se `claude` (Claude Code) está instalado.
2. Checa se `~/.hermes/` existe (Hermes Agent instalado).
3. **Clona um segundo repositório** (`niski84/claude-bridge`) em `~/.local/share/claude-bridge`, roda `go build`.
4. Cria uma **unit systemd de usuário** (`~/.config/systemd/user/claude-bridge.service`) para manter o bridge sempre rodando.
5. Cria um **symlink** de `plugin/claude-cli/` para `~/.hermes/plugins/model-providers/claude-cli`.
6. Escreve `CLAUDE_BRIDGE_URL=http://localhost:9180/v1` em `~/.hermes/.env` (só para o picker reconhecer o provider como "configurado").
7. Faz curl em `/api/health` e `hermes plugins list` para verificar.

**Complexidade operacional real deste passo a passo**: 2 repositórios git, 1 toolchain extra (Go), 1 processo persistente rodando como serviço systemd, 1 symlink, 1 edição de arquivo de configuração do Hermes. Tudo isso existe só para satisfazer o requisito "o provider precisa ter um `base_url` HTTP".

## Comparação direta com o mecanismo oficial nativo do Hermes

O próprio roadmap do README do terceiro admite a limitação:

> - [ ] Optional support for direct subprocess (skip the HTTP hop) when running entirely inside Hermes

Isso **já existe** no Hermes Agent (não era público/documentado quando esses repositórios foram criados, ou o autor simplesmente não pesquisou fundo o bastante — ver [03](./03-modelo-de-provider-do-hermes.md)). É exatamente o gap que a arquitetura unificada deste repositório fecha.

## O que vale a pena herdar

- A ideia central (registrar um `ProviderProfile` com aliases amigáveis: `claude`, `claude-code`, `claude-max`).
- A lista curada de modelos (`sonnet`, `opus`, `haiku` + IDs versionados) — precisa de manutenção manual continuada, é assim em todos os providers do Hermes.
- `default_aux_model="haiku"` — bom default para tarefas auxiliares baratas (compressão de contexto, sumarização, etc.), mantido na arquitetura nova.
- Passo de verificação pós-instalação (smoke test).

## O que **não** deve ser herdado

- Dependência de um segundo repositório clonado em tempo de instalação.
- Unidade systemd para o "bridge" (deixa de existir como processo persistente — ver [04](./04-decisao-bridge-e-necessario.md) e [05](./05-arquitetura-unificada.md)).
- O hack de `env_vars=("CLAUDE_BRIDGE_URL",)` como "credencial falsa" só para aparecer no picker — a nova arquitetura usa `auth_type="external_process"`, que tem semântica própria e correta para esse caso (mesmo padrão do provider `copilot-acp` bundled no Hermes).
