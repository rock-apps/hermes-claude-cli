# 09 — Escopo e migração

Resumo consolidado do que entra e do que fica de fora, com justificativa. Detalhes de cada item nos documentos [01](./01-analise-claude-bridge.md) e [02](./02-analise-hermes-claude-cli-original.md).

## Dentro do escopo (herdado, com correções)

| Funcionalidade | Origem | Mudança em relação ao original |
|---|---|---|
| Provider `claude-cli` no picker do Hermes (`hermes model`) | `hermes-claude-cli` original | Mesmo conceito; `auth_type="external_process"` em vez de `base_url` HTTP + variável de ambiente falsa. |
| Aliases amigáveis (`claude`, `claude-code`, `claude-max`, `claude-subscription`) | `hermes-claude-cli` original | Mantidos como estão. |
| Catálogo de modelos (`sonnet`/`opus`/`haiku` + IDs versionados) | ambos | Mantido; precisa de manutenção manual contínua conforme a Anthropic libera novos modelos — mesma dívida operacional que já existia. |
| Normalização de alias por substring (`sonnet`/`opus`/`haiku`) | `claude-bridge` | Portado para `protocol.py`. |
| Diretórios de leitura configuráveis (`--add-dir`) | `claude-bridge` | Mantido o conceito; removida a lista fixa de diretórios pessoais hardcoded (ver [07](./07-configuracao.md)). |
| Mapeamento `stop_reason` → `finish_reason` | `claude-bridge` | Portado como está (`end_turn`→`stop`, `max_tokens`→`length`, `tool_use`→`tool_calls`). |
| `default_aux_model="haiku"` | `hermes-claude-cli` original | Mantido. |
| Cost/usage accounting | `claude-bridge` (anunciado, mas quebrado) | **Corrigido de fato** — passa a usar `--output-format json`/`stream-json` para extrair `total_cost_usd`/`usage` reais do CLI, em vez de campos sempre zerados. |

## Fora do escopo (não será replicado)

| Item | Origem | Justificativa |
|---|---|---|
| Servidor HTTP dedicado (`cmd/claude-bridge/main.go`) | `claude-bridge` | Substituído por `create_client()`/subprocesso direto — ver [04](./04-decisao-bridge-e-necessario.md). |
| `cmd/model-router/main.go` (roteador Anthropic Messages → DeepSeek/z.ai) | `claude-bridge` | Resolve um problema diferente (trocar o backend de modelo do **próprio Claude Code**, não integrar Claude ao Hermes). Não documentado no README, não referenciado pelo plugin Hermes, veio de um commit "Backup local project state". Scope creep — se a Rock Apps quiser essa funcionalidade (usar DeepSeek/GLM dentro do Claude Code), é um **projeto separado**, não parte deste plugin. |
| `cmd/zai-proxy/main.go` (proxy Anthropic Messages → z.ai) | `claude-bridge` | Mesma justificativa do item acima. |
| Binários versionados (`model-router`, `zai-proxy`, `zai-proxy.bak`, `bin/model-router`, `claude-bridge.pid`) | `claude-bridge` | Erro de higiene de repositório (artefatos de build e PID file não deveriam estar no git). `.gitignore` deste projeto previne isso desde o início. |
| Unidade systemd para o bridge | ambos | Não há mais processo de longa duração a gerenciar. |
| Clonagem de um segundo repositório durante a instalação | `hermes-claude-cli` original (`install.sh`) | Tudo vive em um único repositório agora. |
| `CLAUDE_BRIDGE_URL` como "credencial falsa" para o picker | `hermes-claude-cli` original | `auth_type="external_process"` resolve isso de forma nativa e correta. |
| Suporte a consumidores externos ao Hermes (Open WebUI, LibreChat, Cursor) via o mesmo endpoint HTTP | `claude-bridge` | Fora do escopo declarado pelo usuário ("será um plugin utilizado no hermes"). Registrado como possível modo opcional futuro em [05](./05-arquitetura-unificada.md) e [10](./10-roadmap.md), não como requisito atual. |
| `claude-agent-sdk` (pacote oficial da Anthropic no PyPI, usado por projetos como [`RichardAtCT/claude-code-openai-wrapper`](https://github.com/RichardAtCT/claude-code-openai-wrapper)) como base do `process.py` em vez de `subprocess`+parsing manual do JSON do CLI | avaliado, não adotado | O SDK é assíncrono (`async for` em `query()`) e não bate com o padrão síncrono que o `CopilotACPClient` de referência usa (subprocesso bloqueante) — adotá-lo exigiria ponte assíncrona dentro de `create_client()`, mais uma dependência externa, sem ganho real: já validamos empiricamente o schema JSON real de `claude -p --output-format json` (ver [06](./06-referencia-cli-claude.md)) e ele é simples de parsear com a stdlib. O wrapper citado resolve o mesmo problema que o `claude-bridge` (expõe HTTP), só que com o SDK por baixo em vez de parsing manual — não muda a decisão de [04](./04-decisao-bridge-e-necessario.md) de não precisar de servidor HTTP aqui. Vale reconsiderar o SDK só se um dia quisermos continuidade de sessão nativa (`--resume` gerenciado pelo SDK) em vez do subprocess-por-chamada — ver Fase 4 do [roadmap](./10-roadmap.md). |

## Limitações que persistem (não são resolvidas por nenhuma escolha de arquitetura)

- **Sem passthrough de `tools:` externos** — limitação do próprio `claude` CLI, não do transporte (ver [06](./06-referencia-cli-claude.md)).
- **Overhead de subprocesso por chamada (~1–3s)** — inerente ao `claude` CLI, presente tanto na arquitetura antiga quanto na nova.
- **Sem protocolo ACP nativo no `claude` CLI** — a integração via subprocesso precisa de um parser próprio para o formato de saída do `claude -p`, não pode reaproveitar o parser ACP que o Hermes já tem para o Copilot.
