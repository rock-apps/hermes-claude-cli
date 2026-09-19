# 06 — Reference: `claude` CLI flags this integration relies on

Gathered from `claude --help` on the locally installed version (**Claude Code 2.1.276**). This version does **not** support the ACP protocol (`--acp`) the `copilot` CLI uses — there's no such flag in `claude --help`. That's why this integration uses the CLI's own native protocol (`--print` + `--output-format`), not JSON-RPC/ACP.

## Flags actually used by `process.build_args()`

| Flag | Purpose |
|---|---|
| `-p`, `--print` | Non-interactive mode: print the response and exit. Required for backend use. |
| `--model <alias\|id>` | Selects the model (`sonnet`, `opus`, `haiku`, or a full ID). |
| `--output-format json` | Structured JSON result on stdout — `total_cost_usd`, `usage`, `session_id`, `is_error`, `stop_reason`, `result` are all parsed from this. Verified against a real invocation, not assumed (see [01](./01-analysis-claude-bridge.md) for the bug in the original bridge this fixes: it never passed this flag, so cost/usage were always zero). |
| `--append-system-prompt <text>` | Appends to the default system prompt. Only sent on a fresh (non-resumed) call — see below. |
| `--resume <id>` | Resumes a prior session by the `session_id` a previous call returned, so only the new message(s) need to be sent — see Fase 4 in [10-roadmap.md](./10-roadmap.md). |
| `--add-dir <dirs...>` | Grants read access to directories outside the cwd. Variadic — see the `--` note below. |
| `--dangerously-skip-permissions` | Bypasses the permission system entirely. Available in `process.PermissionConfig.bypass` but not exposed via any environment variable — opt-in only by editing `client.py` directly (see [08-security.md](./08-security.md)). |
| `--permission-mode <mode>` | Values: `acceptEdits`, `auto`, `bypassPermissions`, `manual`, `dontAsk`, `plan`. Defaults to `auto` (`CLAUDE_CLI_PERMISSION_MODE`). |
| `--permission-prompts none` | Always passed (not configurable): anything that would need a human confirmation is denied instead of hanging — there's no human to answer in a headless provider. |
| `--restricted` | Drops Bash/PowerShell/REPL/WebFetch. Defaults to on (`CLAUDE_CLI_RESTRICTED=true`) — see [08-security.md](./08-security.md). |
| `--max-budget-usd <amount>` | Per-call spend cap, exposed as `CLAUDE_CLI_MAX_BUDGET_USD` (unset by default). |
| `--` (separator) | Always inserted right before the prompt. `--add-dir` is variadic, so without this a prompt not starting with `-` gets silently swallowed as one more directory instead of reaching `claude` — a real bug found and fixed during Fase 3, see [08-security.md](./08-security.md). |
| `--output-format stream-json` | Used for `stream=True` calls (`process.run_streaming()`) — real incremental output, one JSON event per line. See Fase 2 in [10-roadmap.md](./10-roadmap.md) for why this was initially skipped, then built after all. |
| `--include-partial-messages` | Required alongside `stream-json` to actually get `content_block_delta` events, not just coarse message-level events. |
| `--verbose` | **Required** alongside `--print --output-format stream-json` — verified empirically: without it the CLI refuses with "requires --verbose" (undocumented in the flag's own `--help` description; this was a real bug caught before `run_streaming` shipped, not a design choice). Harmless for a `--print` invocation — it doesn't add interactive/human-facing output. |

## Investigated, deliberately not used

| Flag | Why not |
|---|---|
| `--input-format stream-json` | Structured stdin input instead of a positional argument — no current need to send messages incrementally. |
| `--session-id <uuid>` | Setting an explicit session id ourselves. Not needed: `--resume <id>` uses the id `claude` already assigned on the prior turn instead. |
| `--json-schema <schema>` | Structured output validation — no current use case for it. |
| `--exclude-dynamic-system-prompt-sections` | Improves prompt-cache reuse across resumed sessions by stripping volatile sections (cwd, git status) from the system prompt. Not needed today: on `--resume`, `--append-system-prompt` isn't even sent (see below), so there's no repeated system-prompt text to strip in the first place. |
| `--safe-mode` | Used by the original `claude-bridge`; dropped — no clear need identified for this integration. |

## System prompt and `--resume` interact

On a resumed call, `client.py` does **not** re-send `--append-system-prompt`: by default the CLI snapshots the system prompt on a session's first request and replays that snapshot on every later request and resume (`--system-prompt-snapshot`, default `on`) — resending it would be redundant.

## What the CLI still can't do (true regardless of architecture)

- **No passthrough for externally-defined `tools:`.** The `claude` CLI doesn't accept tool schemas from a caller — it only knows its own built-in tools (Read, Grep, Bash, Edit, etc.). This limitation, documented by both original third-party projects, persists here too — it's a CLI limitation, not a transport one.
  - **Observed real-world impact** (confirmed on a live Hermes deployment): Hermes' own native tools that are only exposed to the model via the OpenAI-style `tools:` array in the chat completion request — cron/schedule job creation, `RemoteTrigger`, the scheduled-automation skill, kanban, etc. — do not work through `claude-cli`, because that array never reaches the `claude` subprocess. Asking the model (via `claude-cli`) to "schedule a recurring check every hour" correctly results in the model reporting it has no such tool available; the same request against a real OpenAI-compatible provider (e.g. `deepseek` via OpenRouter) works normally, because Hermes can send the tool schemas over the wire.
  - **What still works fine**: MCP-connector-backed lookups (e.g. querying a Slack workspace through an MCP server like Sharp or TLE) were confirmed working correctly through `claude-cli` in the same session. The exact mechanism Hermes uses to bridge those specific calls through a CLI with no tool-schema support wasn't traced end-to-end — but empirically, MCP-server-based data lookups and Hermes-native tool-invocation (cron/RemoteTrigger/skills) are **not** equally affected; only the latter category is broken.
  - **Practical guidance**: for profiles/workflows that depend on Hermes' native scheduling/automation tools, use a real OpenAI-compatible provider (Nous, OpenRouter, etc.) instead of `claude-cli`; reserve `claude-cli` for reasoning/coding/chat and MCP-backed lookups, where it performs well.
  - **Not fixable by switching to the Claude Agent SDK.** The Agent SDK does support custom tool schemas (MCP servers, `allowedTools`) — but it requires `ANTHROPIC_API_KEY` (or a cloud provider auth) and does not support reusing a Claude Max subscription's local OAuth session; Anthropic's own docs state third-party SDK apps may not offer claude.ai login. Adopting it would fix the tool passthrough at the cost of the entire reason this project exists (Max-plan billing instead of per-token API credits). See [09-scope-and-migration.md](./09-scope-and-migration.md) for the full evaluation.
- **No native ACP protocol.** Unlike the `copilot` CLI, `claude` doesn't speak JSON-RPC/ACP today — this integration parses `claude -p`'s own text/JSON output, it can't reuse Hermes' existing ACP parser built for Copilot.
