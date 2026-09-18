# hermes-claude-cli

A model provider plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that exposes the official `claude` CLI (Claude Code), authenticated with a **Claude Max subscription**, as a first-class provider — no HTTP bridge involved.

> **Status**: implemented and validated end-to-end inside a real Hermes Agent install (including the maintainer's own personal instance, post-`hermes update`). 81 tests, `ruff`-clean. See [`docs/10-roadmap.md`](./docs/10-roadmap.md) for what shipped and what's still open, and [`CLAUDE.md`](./CLAUDE.md) for a maintainer-oriented summary.

## Why

Third-party tools that hit the Anthropic API via an API key (or third-party OAuth) bill against Claude Max's "extra usage" credits, not the plan's base allowance — the official `claude` CLI is the only path that uses the base allowance. This plugin lets Hermes Agent use that path, talking to the `claude` CLI directly as a subprocess instead of through an HTTP bridge.

## Install

Prerequisites: [Claude Code](https://claude.ai/code) installed and authenticated, and [Hermes Agent](https://github.com/NousResearch/hermes-agent) installed.

### Option 1 — one command (recommended for using the plugin)

```bash
hermes plugins install rock-apps/hermes-claude-cli/plugin/claude_cli --enable
hermes gateway restart   # if the gateway is already running
```

No manual cloning — `hermes` clones just the plugin subdirectory (not the whole analysis/docs repo), runs it through Hermes' built-in security scanner, and enables it. Then:

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

Configuration is via environment variables (all optional) — see [`docs/07-configuracao.md`](./docs/07-configuracao.md).

## Documentation

Start at [`docs/README.md`](./docs/README.md). Highlights:

- [`docs/04-decisao-bridge-e-necessario.md`](./docs/04-decisao-bridge-e-necessario.md) — why this project does **not** run an HTTP server, unlike the projects that inspired it.
- [`docs/05-arquitetura-unificada.md`](./docs/05-arquitetura-unificada.md) — architecture.
- [`docs/10-roadmap.md`](./docs/10-roadmap.md) — implementation phases and status.

## Reference projects

This plugin replaces and unifies two third-party projects:

- [`niski84/claude-bridge`](https://github.com/niski84/claude-bridge)
- [`niski84/hermes-claude-cli`](https://github.com/niski84/hermes-claude-cli)
