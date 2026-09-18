# 06 — Referência: flags do CLI `claude` relevantes para a integração

Levantado via `claude --help` na versão instalada localmente (**Claude Code 2.1.276**). Esta versão **não** suporta o protocolo ACP (`--acp`) que o `copilot` CLI usa — não existe essa flag no `claude --help`. Por isso a integração usa o protocolo nativo do próprio `claude` CLI (`--print` + `--output-format`), não JSON-RPC/ACP.

## Flags já usadas pelo `claude-bridge` original

| Flag | Efeito |
|---|---|
| `-p`, `--print` | Modo não interativo: imprime resposta e sai. Obrigatório para uso como backend. |
| `--model <alias\|id>` | Seleciona modelo (`sonnet`, `opus`, `haiku` ou ID completo). |
| `--append-system-prompt <texto>` | Acrescenta ao system prompt padrão. |
| `--add-dir <dirs...>` | Concede acesso de leitura a diretórios fora do cwd. |
| `--dangerously-skip-permissions` | Bypassa todo o sistema de permissões (usado pelo bridge original como "modo fácil"). |
| `--safe-mode` | Inicia com todas as customizações (skills/hooks/etc. do usuário) — usado pelo bridge original. |

## Flags que o `claude-bridge` original **não usa** e deveriam ser adotadas

| Flag | Por que importa |
|---|---|
| `--output-format <text\|json\|stream-json>` | O bridge original nunca passa isso — por isso `total_cost_usd`/`usage` nunca são preenchidos de fato (ver [01](./01-analise-claude-bridge.md)). `json` dá uma resposta estruturada única; `stream-json` dá eventos incrementais reais. |
| `--include-partial-messages` | Só funciona com `--output-format stream-json`; entrega chunks de texto conforme são gerados — permite **streaming de verdade** em vez do "fake SSE de 3 chunks" do bridge original. |
| `--input-format <text\|stream-json>` | Permite enviar o prompt via stdin em formato estruturado, em vez de só como argumento posicional — relevante se quisermos, no futuro, enviar mensagens incrementalmente. |
| `--session-id <uuid>` | Define um ID de sessão explícito na primeira chamada. |
| `-r`, `--resume [id]` | Retoma uma conversa por `session-id`, evitando reenviar o histórico inteiro a cada turno (ver v2 em [05](./05-arquitetura-unificada.md)). |
| `--permission-mode <modo>` | Valores: `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. Alternativa mais granular a `--dangerously-skip-permissions` — ver [08](./08-seguranca.md). |
| `--permission-prompts <host\|none>` | `none` = "qualquer coisa que pediria confirmação é automaticamente negada" — bom default para um backend headless que não tem humano para responder ao prompt. |
| `--restricted` | Remove ferramentas de execução de código (Bash, PowerShell, REPL) e WebFetch, a menos que explicitamente permitidas via `--tools`. Reduz a superfície de risco quando o objetivo é só "responder como um provider de chat", não "agir como agente com acesso total ao shell". |
| `--max-budget-usd <valor>` | Teto de gasto por chamada em equivalente de API — rede de segurança de custo que o bridge original não tinha. |
| `--json-schema <schema>` | Validação de saída estruturada — não usado hoje, mas pode ser útil para casos de uso futuros (extração estruturada via o provider). |
| `--exclude-dynamic-system-prompt-sections` | Remove seções voláteis (cwd, git status, etc.) do system prompt — melhora reuso de cache de prompt entre chamadas, relevante se formos usar `--session-id` continuamente. |

## Implicação direta para o design

- v1 deve migrar de "nenhum `--output-format`" para **`--output-format json`** (não-streaming) e **`--output-format stream-json --include-partial-messages`** (streaming), corrigindo o bug de cost-accounting identificado em [01](./01-analise-claude-bridge.md).
- O modo de permissão padrão do plugin deve ser reavaliado (ver [08](./08-seguranca.md)) em vez de simplesmente copiar `--dangerously-skip-permissions` como "caminho fácil".
- `--session-id`/`--resume` são a base técnica da otimização v2 descrita em [05](./05-arquitetura-unificada.md).

## O que **não** existe no CLI (limitações que persistem, independente da arquitetura escolhida)

- **Sem suporte a `tools:` externos.** O `claude` CLI não aceita definições de ferramentas de um chamador externo — ele só conhece suas próprias ferramentas built-in (Read, Grep, Bash, Edit, etc.). Isso significa que, mesmo com a nova arquitetura (subprocesso em vez de HTTP), a limitação "tool-call passthrough não funciona" documentada nos dois repositórios originais **continua existindo**. Não é um problema de transporte, é uma limitação do próprio CLI.
- **Sem protocolo ACP nativo.** Diferente do `copilot` CLI, o `claude` CLI de hoje não fala JSON-RPC/ACP — a integração via subprocesso precisa ser feita no protocolo próprio do `claude -p` (texto/JSON via stdout), não reaproveitando o parser ACP que o Hermes já tem para o Copilot.
