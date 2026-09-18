# 07 — Configuração

Superfície de variáveis de ambiente proposta para o plugin unificado. Nomes prefixados com `CLAUDE_CLI_` para não colidir com variáveis já usadas pelo próprio `claude` CLI (`CLAUDE_BIN` era o nome usado pelo bridge original — mantido como fallback para facilitar migração).

| Variável | Default | Propósito |
|---|---|---|
| `CLAUDE_CLI_BIN` | auto-detecção (`~/.local/bin/claude` → `PATH`) | Caminho do binário `claude`. Mesma lógica de `findClaudeBin()` do bridge original. |
| `CLAUDE_CLI_DEFAULT_MODEL` | `sonnet` | Alias/modelo padrão quando o Hermes não especifica. |
| `CLAUDE_CLI_ALLOWED_DIRS` | (vazio) | Lista separada por `:` de diretórios extras liberados via `--add-dir`. Substitui a lista fixa hardcoded do bridge original (`$HOME/Documents:$HOME/.hermes:$HOME/goprojects`) — sem defaults "mágicos" específicos de um usuário. |
| `CLAUDE_CLI_PERMISSION_MODE` | `dontAsk` (a definir — ver [08](./08-seguranca.md)) | Mapeia para `--permission-mode`. Substitui o binário `CLAUDE_BYPASS_PERMISSIONS=true/false` do original por um valor explícito dentre os modos nativos do CLI. |
| `CLAUDE_CLI_RESTRICTED` | `false` | Se `true`, adiciona `--restricted` (remove Bash/PowerShell/REPL/WebFetch built-ins). |
| `CLAUDE_CLI_MAX_BUDGET_USD` | (vazio = sem limite) | Mapeia para `--max-budget-usd`, teto de gasto por chamada. |
| `CLAUDE_CLI_TIMEOUT_SECONDS` | `300` (paridade com os 5 min do bridge original) | Timeout do subprocesso por chamada. |
| `CLAUDE_CLI_STREAM_MODE` | `stream-json` | `stream-json` (streaming real) ou `json` (uma resposta, força não-streaming mesmo se o Hermes pedir stream). |

## Removidas em relação ao original (e por quê)

| Variável original | Motivo da remoção |
|---|---|
| `PORT` | Não existe mais servidor HTTP (ver [04](./04-decisao-bridge-e-necessario.md)). |
| `CLAUDE_BYPASS_PERMISSIONS` | Substituída por `CLAUDE_CLI_PERMISSION_MODE`, que expõe os modos reais do CLI em vez de um binário ligado/desligado só para `--dangerously-skip-permissions`. |
| `CLAUDE_BRIDGE_URL` (do plugin Hermes original) | Era um hack para o picker do Hermes reconhecer o provider como "configurado". Com `auth_type="external_process"`, essa necessidade desaparece — ver [03](./03-modelo-de-provider-do-hermes.md). |

## Decisão em aberto

O valor default de `CLAUDE_CLI_PERMISSION_MODE` precisa de validação com o usuário: um provider "headless" chamado pelo Hermes automaticamente (sem humano para responder prompts interativos de permissão) praticamente exige `--permission-prompts none` combinado com algum `--permission-mode` que não trave esperando input. As opções e o raciocínio de segurança estão detalhados em [08-seguranca.md](./08-seguranca.md) — este documento só declara a variável, não fixa o valor.
