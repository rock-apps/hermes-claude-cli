# 06 — Reference: `claude` CLI flags this integration relies on

Gathered from `claude --help` on the locally installed version (**Claude Code 2.1.276**). This version does **not** support the ACP protocol (`--acp`) the `copilot` CLI uses — there's no such flag in `claude --help`. That's why this integration uses the CLI's own native protocol (`--print` + `--output-format`), not JSON-RPC/ACP.

## Flags actually used by `process.build_args()`

| Flag | Purpose |
|---|---|
| `-p`, `--print` | Non-interactive mode: print the response and exit. Required for backend use. |
| `--model <alias\|id>` | Selects the model (`sonnet`, `opus`, `haiku`, or a full ID). |
| `--output-format json` | Structured JSON result on stdout — `total_cost_usd`, `usage`, `session_id`, `is_error`, `stop_reason`, `result` are all parsed from this. Verified against a real invocation, not assumed (see [01](./01-analise-claude-bridge.md) for the bug in the original bridge this fixes: it never passed this flag, so cost/usage were always zero). |
| `--append-system-prompt <text>` | Appends to the default system prompt. Only sent on a fresh (non-resumed) call — see below. |
| `--resume <id>` | Resumes a prior session by the `session_id` a previous call returned, so only the new message(s) need to be sent — see Fase 4 in [10-roadmap.md](./10-roadmap.md). |
| `--add-dir <dirs...>` | Grants read access to directories outside the cwd. Variadic — see the `--` note below. |
| `--dangerously-skip-permissions` | Bypasses the permission system entirely. Available in `process.PermissionConfig.bypass` but not exposed via any environment variable — opt-in only by editing `client.py` directly (see [08-seguranca.md](./08-seguranca.md)). |
| `--permission-mode <mode>` | Values: `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. Defaults to `auto` (`CLAUDE_CLI_PERMISSION_MODE`). |
| `--permission-prompts none` | Always passed (not configurable): anything that would need a human confirmation is denied instead of hanging — there's no human to answer in a headless provider. |
| `--restricted` | Drops Bash/PowerShell/REPL/WebFetch. Defaults to on (`CLAUDE_CLI_RESTRICTED=true`) — see [08-seguranca.md](./08-seguranca.md). |
| `--max-budget-usd <amount>` | Per-call spend cap, exposed as `CLAUDE_CLI_MAX_BUDGET_USD` (unset by default). |
| `--` (separator) | Always inserted right before the prompt. `--add-dir` is variadic, so without this a prompt not starting with `-` gets silently swallowed as one more directory instead of reaching `claude` — a real bug found and fixed during Fase 3, see [08-seguranca.md](./08-seguranca.md). |

## Investigated, deliberately not used

| Flag | Why not |
|---|---|
| `--output-format stream-json` + `--include-partial-messages` | Real incremental streaming. Not used because even Hermes' own reference client (`copilot_acp_client.py`) doesn't do real token-by-token delivery for a subprocess provider — see the streaming note in [05](./05-arquitetura-unificada.md) and Fase 2 in [10-roadmap.md](./10-roadmap.md). |
| `--input-format stream-json` | Structured stdin input instead of a positional argument — no current need to send messages incrementally. |
| `--session-id <uuid>` | Setting an explicit session id ourselves. Not needed: `--resume <id>` uses the id `claude` already assigned on the prior turn instead. |
| `--json-schema <schema>` | Structured output validation — no current use case for it. |
| `--exclude-dynamic-system-prompt-sections` | Improves prompt-cache reuse across resumed sessions by stripping volatile sections (cwd, git status) from the system prompt. Not needed today: on `--resume`, `--append-system-prompt` isn't even sent (see below), so there's no repeated system-prompt text to strip in the first place. |
| `--safe-mode` | Used by the original `claude-bridge`; dropped — no clear need identified for this integration. |

## System prompt and `--resume` interact

On a resumed call, `client.py` does **not** re-send `--append-system-prompt`: by default the CLI snapshots the system prompt on a session's first request and replays that snapshot on every later request and resume (`--system-prompt-snapshot`, default `on`) — resending it would be redundant.

## What the CLI still can't do (true regardless of architecture)

- **No passthrough for externally-defined `tools:`.** The `claude` CLI doesn't accept tool schemas from a caller — it only knows its own built-in tools (Read, Grep, Bash, Edit, etc.). This limitation, documented by both original third-party projects, persists here too — it's a CLI limitation, not a transport one.
- **No native ACP protocol.** Unlike the `copilot` CLI, `claude` doesn't speak JSON-RPC/ACP today — this integration parses `claude -p`'s own text/JSON output, it can't reuse Hermes' existing ACP parser built for Copilot.
