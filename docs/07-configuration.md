# 07 — Configuration

Environment-variable surface for the plugin, implemented in `plugin/claude_cli/config.py`. Names are prefixed `CLAUDE_CLI_` to avoid colliding with variables the `claude` CLI itself already uses (`CLAUDE_BIN` is kept as a legacy fallback name).

| Variable | Actual default (implemented) | Purpose |
|---|---|---|
| `CLAUDE_CLI_BIN` | auto-detected (`CLAUDE_BIN` → `~/.local/bin/claude` → `/usr/local/bin/claude` → `PATH`) | Path to the `claude` binary. |
| `CLAUDE_CLI_DEFAULT_MODEL` | `sonnet` | Default alias/model when Hermes doesn't specify one. |
| `CLAUDE_CLI_ALLOWED_DIRS` | (empty) | `:`-separated list of extra directories granted via `--add-dir`. No "magic" defaults tied to a specific user. |
| `CLAUDE_CLI_PERMISSION_MODE` | `auto` | Maps to `--permission-mode`. Always paired with `--permission-prompts none` (not configurable) — see [08-security.md](./08-security.md). |
| `CLAUDE_CLI_RESTRICTED` | `true` | When true (default), adds `--restricted` (drops Bash/PowerShell/REPL/WebFetch). This plugin answers chat messages — it isn't meant to act as an agent with system access. Set `false` for a deployment that wants `claude-cli` to behave as a full agent — see [08-security.md](./08-security.md). |
| `CLAUDE_CLI_MAX_BUDGET_USD` | (empty = no limit) | Maps to `--max-budget-usd`, a per-call spend cap. |
| `CLAUDE_CLI_TIMEOUT_SECONDS` | `300` | Subprocess timeout per call. |
| `CLAUDE_CLI_SESSION_CONTINUITY` | `true` | When true (default), reuses the `claude` CLI session across turns via `--resume` instead of always resending the full history — see Fase 4 in [10-roadmap.md](./10-roadmap.md). Any resume failure falls back automatically to a fresh call with full history. Set `false` to disable entirely. |
| `CLAUDE_CLI_MCP_CONFIG` | (empty) | Maps to `--mcp-config`, passed through as-is (a JSON string or a file path — whatever `claude --mcp-config` itself accepts). Required to make any MCP server visible when `CLAUDE_CLI_RESTRICTED=true` (the default): confirmed empirically that `--restricted` ignores ambient user/project/local settings, so a server registered via `claude mcp add --scope user` is invisible to this plugin's invocations even though it shows up fine in an unrestricted `claude` session. See [`mcp-bridge/README.md`](../mcp-bridge/README.md) for a worked example. |
| `CLAUDE_CLI_ALLOWED_TOOLS` | (empty) | Comma-separated tool names, turned into a `--settings '{"permissions":{"allow":[...]}}'` blob. Same restricted-mode caveat as above: a tool needing approval is silently denied under `--permission-prompts none` unless pre-approved this way — `claude mcp add`'s own registration does not pre-approve anything, and `permissions.allow` in `~/.claude/settings.json` is ignored entirely under `--restricted`. |

There is no `CLAUDE_CLI_STREAM_MODE` (it was in the original plan, never implemented) — streaming doesn't use a dedicated mode; see the `stream=True` note in [05-unified-architecture.md](./05-unified-architecture.md) and Fase 2 in [10-roadmap.md](./10-roadmap.md).

## Multiplexed gateways: `.env` must be the `default` profile's

`gateway.multiplex_profiles: true` (the default for a multi-profile Hermes install) loads the `claude-cli-provider` plugin's code **once, from the `default` profile's installed copy**, and reuses that one loaded module for every routed profile's turns. A copy installed separately under a named profile's own `plugins/` directory (`hermes -p <name> plugins install ...`) is never imported by a multiplexed gateway, no matter how many times it's reinstalled or how correct its `.env` is.

**Practical consequence**: every `CLAUDE_CLI_*` env var in this table — not just `CLAUDE_CLI_MCP_CONFIG`/`CLAUDE_CLI_ALLOWED_TOOLS` — only takes effect under multiplex if it's set in `~/.hermes/.env` (the `default` profile), regardless of which named profile you actually want it to affect. Setting it in `~/.hermes/profiles/<name>/.env` has no effect on a multiplexed gateway's real traffic for that profile.

This was confirmed the hard way on a real deployment: `hermes -z -p <name> ...` (a standalone, non-multiplexed invocation) *does* load the named profile's own plugin copy and `.env` correctly — so a config change kept appearing "fixed" under that test while a real message through the gateway kept failing, until both copies were instrumented with a diagnostic log and only the `default` copy's line fired for a real routed turn. If your own testing only goes through `hermes -z`, it will not catch this — it needs a real message routed through the actual gateway (or `gateway.multiplex_profiles: false`, where each profile's own installed copy and `.env` genuinely run).

A **non-multiplexed** deployment (single profile, or `gateway.multiplex_profiles: false`) does not have this caveat — each profile's own `.env` and plugin copy are what actually execute.

## Subprocess environment (not a `CLAUDE_CLI_*` variable, but affects what the `claude` CLI sees)

Not user-configurable, by design: `process.build_subprocess_env()` only forwards `HOME`, `PATH`, `LANG`/`LC_*`, `TERM`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL` to the subprocess — everything else from Hermes' environment (including `ANTHROPIC_API_KEY` from other providers) is dropped. See [08-security.md](./08-security.md) for why: a leaked `ANTHROPIC_API_KEY` silently overrides Max-subscription auth.
