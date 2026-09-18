# 07 — Configuração

Superfície de variáveis de ambiente do plugin, implementada em `plugin/claude_cli/config.py`. Nomes prefixados com `CLAUDE_CLI_` para não colidir com variáveis já usadas pelo próprio `claude` CLI (`CLAUDE_BIN` era o nome usado pelo bridge original — mantido como fallback).

| Variável | Default real (implementado) | Propósito |
|---|---|---|
| `CLAUDE_CLI_BIN` | auto-detecção (`CLAUDE_BIN` → `~/.local/bin/claude` → `/usr/local/bin/claude` → `PATH`) | Caminho do binário `claude`. |
| `CLAUDE_CLI_DEFAULT_MODEL` | `sonnet` | Alias/modelo padrão quando o Hermes não especifica. |
| `CLAUDE_CLI_ALLOWED_DIRS` | (vazio) | Lista separada por `:` de diretórios extras liberados via `--add-dir`. Sem defaults "mágicos" de um usuário específico (diferente do bridge original). |
| `CLAUDE_CLI_PERMISSION_MODE` | `auto` | Mapeia para `--permission-mode`. Sempre combinado com `--permission-prompts none` (não configurável) — decisão tomada na Fase 1, ver [08-seguranca.md](./08-seguranca.md). |
| `CLAUDE_CLI_RESTRICTED` | `true` | Se `true` (default), adiciona `--restricted` (remove Bash/PowerShell/REPL/WebFetch). Decisão tomada na Fase 3: o caso de uso é "responder uma mensagem de chat", não "agir como agente com acesso ao sistema" — ver [08-seguranca.md](./08-seguranca.md). Setar `false` explicitamente para um deployment que quer o `claude-cli` como agente completo. |
| `CLAUDE_CLI_MAX_BUDGET_USD` | (vazio = sem limite) | Mapeia para `--max-budget-usd`, teto de gasto por chamada. |
| `CLAUDE_CLI_TIMEOUT_SECONDS` | `300` (paridade com os 5 min do bridge original) | Timeout do subprocesso por chamada. |

Não existe `CLAUDE_CLI_STREAM_MODE` (estava no plano original, nunca implementado): streaming não usa um modo dedicado — ver a nota sobre `stream=True` em [05-arquitetura-unificada.md](./05-arquitetura-unificada.md) e a Fase 2 em [10-roadmap.md](./10-roadmap.md).

## Removidas em relação ao original (e por quê)

| Variável original | Motivo da remoção |
|---|---|
| `PORT` | Não existe mais servidor HTTP (ver [04](./04-decisao-bridge-e-necessario.md)). |
| `CLAUDE_BYPASS_PERMISSIONS` | Substituída por `CLAUDE_CLI_PERMISSION_MODE`, que expõe os modos reais do CLI em vez de um binário ligado/desligado só para `--dangerously-skip-permissions`. |
| `CLAUDE_BRIDGE_URL` (do plugin Hermes original) | Era um hack para o picker do Hermes reconhecer o provider como "configurado". Com `auth_type="external_process"`, essa necessidade desaparece — ver [03](./03-modelo-de-provider-do-hermes.md). |

## Ambiente do subprocesso (não é uma variável `CLAUDE_CLI_*`, mas afeta o que o `claude` CLI vê)

Não configurável pelo usuário, por design: `process.build_subprocess_env()` só repassa `HOME`, `PATH`, `LANG`/`LC_*`, `TERM`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL` ao subprocesso — tudo mais do ambiente do Hermes (incluindo `ANTHROPIC_API_KEY` de outros providers) é descartado. Ver [08-seguranca.md](./08-seguranca.md) para o porquê (achado crítico: `ANTHROPIC_API_KEY` vazada sobrescreve a autenticação Max).
