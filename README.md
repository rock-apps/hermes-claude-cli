# hermes-claude-cli

A model provider plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that exposes the official `claude` CLI (Claude Code), authenticated with a **Claude Max subscription**, as a first-class provider — no HTTP bridge involved.

> **Status**: implemented and validated end-to-end inside real Hermes Agent installs, including production. 106 tests in the plugin + 58 in [`mcp-bridge/`](./mcp-bridge/), `ruff`-clean. See [`docs/08-roadmap.md`](./docs/08-roadmap.md) for what shipped and what's still open, and [`CLAUDE.md`](./CLAUDE.md) for a maintainer-oriented summary.

## Why

Third-party tools that hit the Anthropic API via an API key (or third-party OAuth) bill against Claude Max's "extra usage" credits, not the plan's base allowance — the official `claude` CLI is the only path that uses the base allowance. This plugin lets Hermes Agent use that path, talking to the `claude` CLI directly as a subprocess instead of through an HTTP bridge.

## Install

Prerequisites: [Claude Code](https://claude.ai/code) installed and authenticated, and [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed.

### Option 1 — one command (recommended for using the plugin)

```bash
hermes plugins install rock-apps/hermes-claude-cli/plugin/claude_cli --enable
hermes gateway restart   # if the gateway is already running
```

No manual cloning — `hermes` clones just the plugin subdirectory, runs it through Hermes' built-in security scanner, and enables it. Then:

```bash
hermes model   # look for "Claude CLI (Max subscription)"
```

Update later with `hermes plugins update claude-cli-provider`.

### Option 2 — manual clone (recommended for developing this plugin)

```bash
git clone https://github.com/rock-apps/hermes-claude-cli.git
cd hermes-claude-cli
./scripts/install.sh
```

This symlinks `plugin/claude_cli/` into `$HERMES_HOME/plugins/model-providers/claude-cli` (default `~/.hermes`), so local edits apply immediately without reinstalling — this is the flow used to develop this project. No build step, no systemd unit.

Configuration is via environment variables (all optional) — see [`docs/05-configuration.md`](./docs/05-configuration.md).

## Known limitations

- **Hermes' native tools (cron/schedule creation, `RemoteTrigger`, kanban, etc.) don't work through this provider by default.** The `claude` CLI doesn't accept externally-defined tool schemas — it only knows its own built-in tools. Hermes exposes its native tools to the model via the OpenAI-style `tools:` request field, which never reaches the `claude` subprocess, so the model has no way to know those tools exist. Confirmed on a live deployment: asking for a recurring scheduled check correctly gets "I don't have that tool" from `claude-cli`, while the identical request against an OpenAI-compatible provider (e.g. `deepseek` via OpenRouter) works normally.
  - MCP-connector-backed lookups (e.g. a Slack workspace search through an MCP server) were confirmed working fine through `claude-cli` in the same session — this limitation is specific to Hermes-native tool-calling, not MCP data access in general.
  - **Fixed for cron/kanban specifically by [`mcp-bridge/`](./mcp-bridge/)**, a small MCP server (in this same repo) that wraps the `hermes cron`/`hermes kanban` CLI commands and registers with `claude mcp add` — MCP servers are configured persistently, independent of the per-request `tools:` limitation. Confirmed working end-to-end against a real Max-subscription session (no `ANTHROPIC_API_KEY`). See [`mcp-bridge/README.md`](./mcp-bridge/README.md).
  - For anything not covered by that bridge (`delegate_task`, arbitrary future Hermes tools): use a different provider for that profile/workflow; use `claude-cli` for reasoning, coding, and chat. See [`docs/04-claude-cli-reference.md`](./docs/04-claude-cli-reference.md#what-the-cli-still-cant-do-true-regardless-of-architecture) for details.
  - **This is not fixable by switching to the Claude Agent SDK** (as a wholesale replacement for the `claude -p` subprocess approach). The Agent SDK supports custom tools but its documented policy requires `ANTHROPIC_API_KEY` billing — it does not support reusing a Claude Max subscription's OAuth session for third-party tools, per Anthropic's own docs. Evaluated and rejected as a full replacement; see [`docs/07-scope-and-migration.md`](./docs/07-scope-and-migration.md) (which also notes the SDK's actual source code just wraps the same local `claude` binary this plugin already uses — a nuance on the policy, not a reversal of the rejection).

## Documentation

Start at [`docs/README.md`](./docs/README.md). Highlights:

- [`docs/02-is-bridge-necessary.md`](./docs/02-is-bridge-necessary.md) — why this project does **not** run an HTTP server.
- [`docs/03-unified-architecture.md`](./docs/03-unified-architecture.md) — architecture.
- [`docs/08-roadmap.md`](./docs/08-roadmap.md) — implementation phases and status.
