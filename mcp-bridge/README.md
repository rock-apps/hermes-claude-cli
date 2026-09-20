# hermes-mcp-bridge

An MCP server that exposes Hermes Agent's own `cron` and `kanban` CLI subcommands as MCP tools, so a Hermes profile running on the [`claude-cli` provider](../README.md) can use them.

## Why this exists

The `claude` CLI accepts no per-request tool schemas from its caller — Hermes' native tools (`cronjob_manage`, `kanban_create`, `delegate_task`, etc.) are only exposed to a model via the OpenAI-style `tools:` request field, which never reaches a `claude -p` subprocess. See [`../docs/04-claude-cli-reference.md`](../docs/04-claude-cli-reference.md#what-the-cli-still-cant-do-true-regardless-of-architecture) for the full limitation.

The `claude` CLI *does* support persistently configured MCP servers (`claude mcp add`), independent of per-request tool passthrough. This package is that: a small MCP server, backed entirely by shelling out to the already-existing `hermes cron`/`hermes kanban` CLI commands (not Hermes' internal Python APIs — those aren't a supported external interface), that gives a `claude-cli`-backed conversation real access to scheduling and cross-profile task delegation, without leaving the Max-subscription OAuth path.

Confirmed working end-to-end against this plugin's *actual* invocation shape (2026-09-19, local dev machine and `muse` production deployment): `auth status` showing `authMethod: claude.ai` / `subscriptionType: max` / no `ANTHROPIC_API_KEY` set, `claude -p --restricted --permission-prompts none --mcp-config ... --settings ...` (exactly what `client.py`/`process.py` build) successfully calling `cron_status`, `cron_list`, and `kanban_create`, `permission_denials: []` in the raw JSON result.

## What it does NOT solve

This bridge only covers the `hermes cron` and `hermes kanban` CLI surfaces — deliberately, because those are genuine, documented, external CLI commands (see `hermes cron --help` / `hermes kanban --help`), not Hermes-internal functions being reverse-engineered. `delegate_task` (in-process subagents) has no equivalent standalone CLI command and is out of scope here.

## Install

```bash
cd mcp-bridge
uv venv .venv && uv pip install --python .venv/bin/python -e .
```

## Register with this plugin — NOT `claude mcp add` alone

`claude mcp add --scope user` looks like the natural way to register this server, and it works fine for an interactive `claude` session. **It does not work for this plugin.** `CLAUDE_CLI_RESTRICTED` defaults to `true`, which passes `--restricted` — and `--restricted`'s own `--help` text says it "ignores user, project and local settings files." Confirmed empirically (2026-09-19, `muse`): an MCP server registered via `claude mcp add --scope user` is **completely invisible** to a `--restricted` invocation — not merely permission-denied, the model reports zero tools with "hermes" or "bridge" in the name at all. The one documented exception is passing `--mcp-config`/`--settings` explicitly per invocation, which `--restricted` does not ignore — so that's what this plugin does, via two config env vars wired straight into `process.build_args()`.

Configure the **Hermes profile's own `.env`**:

```bash
# .env (e.g. ~/.hermes/profiles/rockapps/.env)
CLAUDE_CLI_MCP_CONFIG={"mcpServers":{"hermes-bridge-rockapps":{"command":"/absolute/path/to/mcp-bridge/.venv/bin/hermes-mcp-bridge","env":{"HERMES_MCP_PROFILE":"rockapps"}}}}
CLAUDE_CLI_ALLOWED_TOOLS=mcp__hermes-bridge-rockapps__cron_list,mcp__hermes-bridge-rockapps__cron_create,mcp__hermes-bridge-rockapps__cron_pause,mcp__hermes-bridge-rockapps__cron_resume,mcp__hermes-bridge-rockapps__cron_remove,mcp__hermes-bridge-rockapps__cron_status,mcp__hermes-bridge-rockapps__kanban_list,mcp__hermes-bridge-rockapps__kanban_show,mcp__hermes-bridge-rockapps__kanban_create,mcp__hermes-bridge-rockapps__kanban_assign,mcp__hermes-bridge-rockapps__kanban_comment,mcp__hermes-bridge-rockapps__kanban_complete,mcp__hermes-bridge-rockapps__kanban_block
```

`CLAUDE_CLI_MCP_CONFIG` is passed straight through to `--mcp-config` (this plugin does no parsing of it). `CLAUDE_CLI_ALLOWED_TOOLS` is a comma-separated list this plugin turns into `--settings '{"permissions":{"allow":[...]}}'` itself — see [`../docs/05-configuration.md`](../docs/05-configuration.md).

**⚠️ Under a multiplexed gateway (`gateway.multiplex_profiles: true`, the default for multi-profile Hermes installs), this `.env` MUST be the `default` profile's — `~/.hermes/.env`, not `~/.hermes/profiles/<name>/.env` — regardless of which named profile you actually want this to serve.**

This was the hard-won finding behind getting this bridge working for real (not just in isolated `hermes -z` tests) on the `muse` deployment: a multiplexed gateway loads the `claude-cli-provider` plugin's code **once, from the `default` profile's installed copy**, and reuses that single loaded module for every routed profile's turns. A copy of the plugin installed separately under a named profile's own `plugins/` directory (e.g. via `hermes -p rockapps plugins install ...`) is never imported by a multiplexed gateway — confirmed by instrumenting both copies with a one-line diagnostic log and watching only the `default` copy's log line appear when a real Slack message landed. `hermes -z -p rockapps ...` (a standalone, non-multiplexed invocation) *does* load the named profile's own copy — which is exactly why it kept testing "fixed" while the real Slack path kept failing, until this was found. If you only test through `hermes -z`, you can ship a config that silently never applies to real gateway traffic.

Restart the gateway (`hermes gateway restart`) after editing `.env` — and restart it *fully*, not mid-drain: a still-draining old process can pick up a Slack turn before the new one takes over, serving stale config for that one turn. Wait for `hermes gateway status` to stop reporting "draining" (or just `systemctl --user restart hermes-gateway.service` directly) before considering the config live.

**Security implication, explicit on purpose**: `CLAUDE_CLI_ALLOWED_TOOLS` pre-approves *write* actions too (`cron_create`, `cron_remove`, `kanban_complete`, ...) — the model can create/delete scheduled jobs and complete/block kanban tasks from a chat message with no human approval step. That's the whole point of building this bridge, but it's worth being deliberate about which tool names go in that list rather than pasting the full set above without reading it. For read-only access, only include `cron_list`/`cron_status`/`kanban_list`/`kanban_show`.

**No real per-profile isolation under multiplex.** Because the config lives in the `default` profile's `.env` and is shared by every routed profile's `claude-cli` turns, *every* profile that uses the `claude-cli` provider on a multiplexed gateway sees the *same* `CLAUDE_CLI_MCP_CONFIG`/`CLAUDE_CLI_ALLOWED_TOOLS` — including the same bridge, hardcoded to the same `HERMES_MCP_PROFILE`. A bridge configured with `HERMES_MCP_PROFILE=rockapps` is reachable from an `erick`-profile conversation too, and any action it takes still runs as `rockapps`, not `erick`. If multiple profiles need this bridge acting as themselves, register multiple MCP servers under different names in the same `CLAUDE_CLI_MCP_CONFIG` (one per profile, each with its own `HERMES_MCP_PROFILE`) and include all their tools in `CLAUDE_CLI_ALLOWED_TOOLS` — every profile will see all of them, so this is exposure, not isolation; there's no way to hide one profile's bridge from another's `claude-cli` turns on a multiplexed gateway today. A non-multiplexed (single-profile, or `gateway.multiplex_profiles: false`) deployment does not have this problem — each profile's own `.env` and installed plugin copy are what actually run.

Environment variables the bridge itself reads (distinct from the `CLAUDE_CLI_*` ones above, which belong to this repo's `plugin/`, not to `mcp-bridge/`):

| Variable | Purpose | Default |
|---|---|---|
| `HERMES_MCP_PROFILE` | Appends `-p <profile>` to every `hermes` call this bridge makes. Set it in the `env` block of `CLAUDE_CLI_MCP_CONFIG` above. | unset — targets the default profile |
| `HERMES_MCP_BIN` | Path to the `hermes` binary, if not on `PATH`. | `hermes` |

## Tools exposed

| Tool | Wraps |
|---|---|
| `cron_list` | `hermes cron list [--all]` |
| `cron_create` | `hermes cron create <schedule> [prompt] [--name] [--deliver] [--repeat] [--continuity] [--model] [--provider] [--reasoning-effort] [--paused]` |
| `cron_pause` / `cron_resume` / `cron_remove` | `hermes cron pause/resume/remove <job_id>` |
| `cron_status` | `hermes cron status` |
| `kanban_list` | `hermes kanban list [--assignee] [--status] [--mine]` |
| `kanban_show` | `hermes kanban show <task_id>` |
| `kanban_create` | `hermes kanban create <title> [--assignee] [--body]` |
| `kanban_assign` | `hermes kanban assign <task_id> <profile>` |
| `kanban_comment` | `hermes kanban comment <task_id> <text>` |
| `kanban_complete` | `hermes kanban complete <task_id> [--summary]` |
| `kanban_block` | `hermes kanban block <task_id> <reason>` |

## Development

```bash
.venv/bin/python -m pytest -q     # 37 tests, no real subprocess calls (subprocess.run is mocked)
.venv/bin/ruff check .
```

`hermes_mcp/runner.py` is the only module that touches `subprocess`; `cron_tools.py`/`kanban_tools.py` are plain, synchronous functions tested by mocking `run_hermes` directly — `server.py` only wires them into an `mcp.server.mcpserver.MCPServer` instance and adds no logic of its own.
