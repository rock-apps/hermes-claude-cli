# 01 — Análise: `niski84/claude-bridge`

Repositório: https://github.com/niski84/claude-bridge (Go, MIT, ~9 commits, "Status: Working").

## O que o README/ENDPOINTS.md declaram

Um servidor HTTP em Go (~350 LOC, um único arquivo, zero dependências externas) que expõe:

- `POST /v1/chat/completions` — compatível com OpenAI Chat Completions (streaming e não-streaming).
- `GET /v1/models` — lista estática de aliases (`sonnet`, `opus`, `haiku` + IDs completos).
- `GET /api/health` — liveness.
- `GET /` — texto de ajuda.

Cada request HTTP dispara um `exec.Command` do binário `claude`, no modo `-p --print --model <alias> --safe-mode [--append-system-prompt ...] [--add-dir ... | --dangerously-skip-permissions] <prompt>`, aguarda a saída, e devolve como uma resposta OpenAI (ou finge streaming SSE em 3 chunks).

## Auditoria do código real (`cmd/claude-bridge/main.go`, 518 linhas)

Confirma o que o README diz, com detalhes relevantes que o README omite:

- **Achatamento de conversa (`flattenMessages`)**: todo o histórico (exceto a última mensagem `user`) é serializado em texto puro (`"USER:\n..."`, `"ASSISTANT:\n..."`) e injetado como prefixo do prompt final. Isso significa que **cada chamada reenvia a conversa inteira como texto**, sem usar o suporte nativo do `claude` CLI a sessões (`--session-id`/`--resume` — ver [06](./06-referencia-cli-claude.md)). Efeito prático: gasta mais tokens de entrada a cada turno e não se beneficia de cache de prompt entre turnos.
- **Streaming é falso**: com `stream: true`, o bridge não usa `--output-format stream-json` do `claude` CLI. Ele espera a resposta completa (`--output-format` sequer é passado — o parsing de JSON no código lê a saída como texto puro, não como o JSON estruturado que `claude -p --output-format json` retornaria) e emite exatamente 3 eventos SSE (role, conteúdo completo, finish). Do ponto de vista do cliente há "streaming", mas não há token-a-token real.
- **Bug/inconsistência não documentada**: o código declara o tipo `claudeJSONResult` com campos `TotalCostUSD`, `Usage.InputTokens/OutputTokens`, `SessionID`, mas a chamada real ao CLI **não passa `--output-format json`** (só usa `-p --print`), então `cmd.Output()` retorna texto puro, não JSON. O struct é preenchido manualmente (`result.Result = string(out)`) e os campos de custo/uso/sessão **ficam sempre zerados/genéricos** (`SessionID` é gerado localmente com timestamp, não vem do CLI). Ou seja: o "cost accounting" que o README anuncia como feature (`[claude-bridge] sonnet: in=3 out=458 cost=$0.0705 ...`) está **quebrado na prática** — sempre loga `in=0 out=0 cost=$0.0000`, a menos que uma versão do binário compilado (não o `main.go` do commit HEAD) realmente use `--output-format json`. Isso é uma discrepância entre documentação e implementação que não deve ser replicada.
- **Permissões**: por padrão usa `--add-dir` para uma lista fixa de diretórios (`$HOME/Documents`, `$HOME/.hermes`, `$HOME/goprojects`), configurável via `CLAUDE_ALLOWED_DIRS`. Alternativa é `CLAUDE_BYPASS_PERMISSIONS=true` → `--dangerously-skip-permissions`, documentado como risco aceito.
- **Sem autenticação**: bind é `:PORT` (não `127.0.0.1:PORT` explicitamente — o Go `http.Server{Addr: ":9180"}` escuta em **todas as interfaces**, não só loopback, apesar do README dizer "Localhost only. The bridge does not bind to 0.0.0.0 by default"). Isso é uma **imprecisão de segurança no próprio README**: `:9180` no Go é equivalente a `0.0.0.0:9180`, não a `127.0.0.1:9180`. Qualquer processo na mesma rede (não só na mesma máquina) pode, em tese, alcançar a porta se não houver firewall bloqueando — o que contradiz a afirmação do README de que é "não exposto".

## Binários não documentados encontrados no repositório

Um único commit, `85facf2 "Backup local project state"`, introduziu simultaneamente:

- `cmd/model-router/main.go` (254 linhas) — um roteador Anthropic Messages API (`/v1/messages`) que decide entre backends **DeepSeek** e **z.ai/GLM** por prefixo do nome do modelo (`deepseek-*`, `glm-*`, `zai-*`). Serve para usar o **próprio Claude Code** (não o Hermes) com modelos de terceiros via `ANTHROPIC_BASE_URL`.
- `cmd/zai-proxy/main.go` (516 linhas) — proxy Anthropic Messages → OpenAI Chat Completions especificamente para a z.ai (GLM-5.2), com o mesmo propósito (fazer o Claude Code falar com um modelo que não é da Anthropic).
- Artefatos binários **versionados por engano**: `model-router`, `zai-proxy`, `zai-proxy.bak`, `bin/model-router`, `claude-bridge.pid`.

**Nenhum desses três itens é mencionado no README, no ENDPOINTS.md, ou no plugin do Hermes.** São ferramentas para um problema ortogonal (trocar o backend de modelo do próprio Claude Code) e não têm relação com "usar o Claude Max dentro do Hermes Agent". Ver conclusão sobre escopo em [09](./09-escopo-e-migracao.md).

## Riscos e dívidas técnicas identificadas

| Item | Risco | Necessário replicar? |
|---|---|---|
| Bind em `:PORT` (todas interfaces) em vez de `127.0.0.1:PORT` | Médio — exposição de rede não intencional | Não se a nova arquitetura eliminar o servidor HTTP (ver [04](./04-decisao-bridge-e-necessario.md)) |
| Sem autenticação na API HTTP | Alto — qualquer processo local (ou de rede, dado o bind) pode consumir a assinatura | Idem acima |
| `--dangerously-skip-permissions` como opção "fácil" | Alto — acesso irrestrito ao filesystem do usuário | Reavaliar modos de permissão nativos do CLI (ver [06](./06-referencia-cli-claude.md) e [08](./08-seguranca.md)) |
| Cost accounting quebrado (campos sempre zerados) | Baixo (cosmético), mas engana o operador | Corrigir: usar `--output-format json` de fato |
| "Streaming" falso (3 chunks) | Baixo/médio — UX pior que o necessário | O CLI suporta `--output-format stream-json --include-partial-messages`; a nova arquitetura deve usar isso de verdade |
| Achatamento de conversa a cada turno | Médio — custo de tokens, sem cache de sessão | O CLI suporta `--session-id`/`--resume`; avaliar para v2 |
| Binários e `.pid` versionados no git | Baixo (higiene de repo) | Não — `.gitignore` estrito desde o início |
| `model-router` / `zai-proxy` fora de escopo, não documentados | Baixo, mas é scope creep | Não replicar agora — ver [09](./09-escopo-e-migracao.md) |

## O que efetivamente vale a pena herdar (parity funcional)

- Normalização de alias de modelo (`sonnet`/`opus`/`haiku` + IDs completos) por substring matching.
- Conceito de diretórios permitidos configuráveis (`CLAUDE_ALLOWED_DIRS`) — mas reavaliar o modo "bypass total" como padrão.
- Endpoint de health-check equivalente (mesmo sem servidor HTTP, precisa de um "self-check": o CLI existe? está autenticado?).
- Mapeamento de `stop_reason` do Claude para `finish_reason` do formato OpenAI (`end_turn`→`stop`, `max_tokens`→`length`, `tool_use`→`tool_calls`).
