# hermes-mcp-bridge

An MCP server that exposes Hermes Agent's own `cron` and `kanban` CLI subcommands as MCP tools, so a Hermes profile running on the [`claude-cli` provider](../README.md) can use them.

## Why this exists

The `claude` CLI accepts no per-request tool schemas from its caller — Hermes' native tools (`cronjob_manage`, `kanban_create`, `delegate_task`, etc.) are only exposed to a model via the OpenAI-style `tools:` request field, which never reaches a `claude -p` subprocess. See [`../docs/06-claude-cli-reference.md`](../docs/06-claude-cli-reference.md#what-the-cli-still-cant-do-true-regardless-of-architecture) for the full limitation.

The `claude` CLI *does* support persistently configured MCP servers (`claude mcp add`), independent of per-request tool passthrough. This package is that: a small MCP server, backed entirely by shelling out to the already-existing `hermes cron`/`hermes kanban` CLI commands (not Hermes' internal Python APIs — those aren't a supported external interface), that gives a `claude-cli`-backed conversation real access to scheduling and cross-profile task delegation, without leaving the Max-subscription OAuth path.

Confirmed working end-to-end (2026-09-19, local dev machine): registered via `claude mcp add`, `auth status` showing `authMethod: claude.ai` / `subscriptionType: max` / no `ANTHROPIC_API_KEY` set, `claude -p` successfully calling `cron_status`, `cron_list`, and `kanban_create` and getting real results back from a live Hermes install.

## What it does NOT solve

This bridge only covers the `hermes cron` and `hermes kanban` CLI surfaces — deliberately, because those are genuine, documented, external CLI commands (see `hermes cron --help` / `hermes kanban --help`), not Hermes-internal functions being reverse-engineered. `delegate_task` (in-process subagents) has no equivalent standalone CLI command and is out of scope here.

## Install

```bash
cd mcp-bridge
uv venv .venv && uv pip install --python .venv/bin/python -e .
```

## Register with the `claude` CLI

For the **default** Hermes profile:

```bash
claude mcp add hermes-bridge --scope user -- "$(pwd)/.venv/bin/hermes-mcp-bridge"
```

For a **named** profile (every action runs as `hermes -p <profile> ...`):

```bash
claude mcp add hermes-bridge --scope user -e HERMES_MCP_PROFILE=rockapps -- "$(pwd)/.venv/bin/hermes-mcp-bridge"
```

`--scope user` registers it globally for the current OS user (every `claude` invocation, from any directory, sees it) — this matters because this plugin's subprocess spawns don't currently pass a per-profile `cwd`, so `--scope local`/`project` (directory-scoped) isn't a way to get per-profile isolation today. If you need *different* Hermes profiles to see *different* MCP-bridge configuration (e.g. one pinned to `rockapps`, another to `erick`), register the bridge under **different tool names** (`claude mcp add hermes-bridge-rockapps ... -e HERMES_MCP_PROFILE=rockapps`, `claude mcp add hermes-bridge-erick ... -e HERMES_MCP_PROFILE=erick`) and tell each profile's system prompt which one to use — there's no way today for the bridge to auto-detect which profile is asking.

Environment variables the bridge itself reads (set via `claude mcp add -e KEY=value`):

| Variable | Purpose | Default |
|---|---|---|
| `HERMES_MCP_PROFILE` | Appends `-p <profile>` to every `hermes` call this bridge makes. | unset — targets the default profile |

## Required extra step: pre-approve the tools

This plugin runs `claude -p` with `--permission-prompts none` (deliberately — see the main [README](../README.md#project-conventions): it answers chat messages, it doesn't act as an unattended agent that can prompt a human). Any tool call that would need approval — which MCP tools do by default, even ones you yourself registered with `claude mcp add` — is **silently denied** in that mode, with no error surfaced back through the chat. Confirmed directly: a `cron_status` call was denied until this step was done, with `claude`'s own output reading "the call was blocked ... denied automatically."

Add every tool name to `permissions.allow` in `~/.claude/settings.json` (the same OS user your Hermes gateway runs as), matching the server name you registered:

```json
{
  "permissions": {
    "allow": [
      "mcp__hermes-bridge-rockapps__cron_list",
      "mcp__hermes-bridge-rockapps__cron_create",
      "mcp__hermes-bridge-rockapps__cron_pause",
      "mcp__hermes-bridge-rockapps__cron_resume",
      "mcp__hermes-bridge-rockapps__cron_remove",
      "mcp__hermes-bridge-rockapps__cron_status",
      "mcp__hermes-bridge-rockapps__kanban_list",
      "mcp__hermes-bridge-rockapps__kanban_show",
      "mcp__hermes-bridge-rockapps__kanban_create",
      "mcp__hermes-bridge-rockapps__kanban_assign",
      "mcp__hermes-bridge-rockapps__kanban_comment",
      "mcp__hermes-bridge-rockapps__kanban_complete",
      "mcp__hermes-bridge-rockapps__kanban_block"
    ]
  }
}
```

**Security implication, explicit on purpose**: this pre-approves *write* actions too (`cron_create`, `cron_remove`, `kanban_complete`, ...) — the model can create/delete scheduled jobs and complete/block kanban tasks from a chat message with no human approval step, same as it already can edit files or run allowlisted `Bash` commands in this same settings file. That's the whole point of building this bridge, but it's worth being deliberate about rather than pasting the block above without reading it. If you only want read access, pre-approve only `cron_list`/`cron_status`/`kanban_list`/`kanban_show` and leave the rest to prompt (which, under `--permission-prompts none`, means they'll just be denied rather than actually asking anyone).
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
