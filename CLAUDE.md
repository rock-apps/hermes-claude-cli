# CLAUDE.md — hermes-claude-cli

Project instructions for Claude Code sessions working in this repository. Read this before touching code.

## What this project is

A model provider plugin for **[Hermes Agent](https://github.com/NousResearch/hermes-agent)** (Nous Research) that exposes the official `claude` CLI (Claude Code), authenticated with a **Claude Max subscription**, as a first-class provider (`hermes model` → "Claude CLI (Max subscription)"). Also ships [`mcp-bridge/`](./mcp-bridge/), a small MCP server giving that provider access to Hermes' own `cron`/`kanban` tools despite the CLI's lack of per-request tool passthrough.

**The reasoning behind the decisions below lives in [`docs/`](./docs/README.md). Read `docs/README.md` first to find the right document.**

## Status

Implemented and validated end-to-end, including against real production deployments and via `hermes plugins install`. 106 automated tests in the plugin (`pytest`, none call the real CLI) + 58 in `mcp-bridge/`, `ruff check` clean. Dev environment: local `.venv/` via `uv` (`python3 -m venv` doesn't work on this system — missing `python3-venv`).

```
cd /mnt/dev/projects-rk/hermes-claude-cli
.venv/bin/python -m pytest -q
```

See `docs/08-roadmap.md` for the full phase-by-phase history and what's still open (real token-by-token streaming — deliberately not built; see below).

## Core architectural decision (don't reopen without new evidence)

**This plugin does not run an HTTP server.** That approach was evaluated and rejected in [`docs/02-is-bridge-necessary.md`](./docs/02-is-bridge-necessary.md). Instead it uses Hermes Agent's native mechanism for non-HTTP providers:

- `ProviderProfile(auth_type="external_process", process_command="claude", ...)`
- `ProviderProfile.create_client()` overridden to return a custom client that talks to the `claude` CLI over subprocess/stdio — **no socket, no port**.
- Same pattern as Hermes Agent's own bundled reference provider: `plugins/model-providers/copilot-acp/` + `agent/copilot_acp_client.py` (see `docs/01-hermes-provider-model.md`).

If a future session considers "adding an HTTP server back", read `docs/02-is-bridge-necessary.md` and `docs/07-scope-and-migration.md` first — there's exactly one documented scenario where that would make sense (reuse by non-Hermes tools), tracked as an optional, undemanded Fase 6.

## Project conventions

- **One repository, one language (Python).** No Go, no compiled binaries, no external toolchain dependency — that's the exact complexity this project removes.
- **No long-running processes.** The `claude` CLI is invoked as a subprocess per call, optionally reused across turns via `--resume` for session continuity (see `plugin/claude_cli/session.py`) — never as a systemd daemon.
- **Small, single-responsibility modules** under `plugin/claude_cli/` (`client.py`, `protocol.py`, `process.py`, `config.py`, `models.py`, `session.py`) — full layout in `docs/03-unified-architecture.md`.
- **Strict `.gitignore`**: never commit binaries, `.pid` files, or build artifacts.
- **TDD** for message-translation logic (`protocol.py`) — write the test first, AAA pattern (Arrange-Act-Assert).
- **The subprocess environment is allowlisted, not blocklisted** (`process.build_subprocess_env`) — only `HOME`, `PATH`, `LANG`/`LC_*`, `TERM`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL` are forwarded. This isn't incidental: `ANTHROPIC_API_KEY`, if forwarded, silently overrides the CLI's OAuth/Max-subscription session and makes it bill against that key instead — confirmed empirically. Don't loosen this without re-reading `docs/06-security.md`.
- **`CLAUDE_CLI_RESTRICTED` defaults to `true`** (`--restricted`, no Bash/PowerShell/REPL/WebFetch) and **`CLAUDE_CLI_PERMISSION_MODE` defaults to `auto`** + `--permission-prompts none` — this plugin answers chat messages, it doesn't act as an unattended agent with system access. Both are deliberate, validated defaults, not placeholders.

## External references (verify before reusing — this moves fast)

- Hermes Agent source (`providers/base.py`, `providers/__init__.py`, `plugins/model-providers/copilot-acp/`, `agent/copilot_acp_client.py`, `agent/agent_runtime_helpers.py`) — read from a clone of `github.com/NousResearch/hermes-agent`. This is an extremely fast-moving monorepo (tens of thousands of commits between two clones taken hours apart during this project's own development); reclone and diff before assuming an API (`create_client`, `auth_type="external_process"`, `process_command`) is still shaped the same way. Older Hermes installs may lack this mechanism entirely — see `docs/08-roadmap.md` for the exact incompatibility and fix (`hermes update`).
- `claude --help` output — flags documented in `docs/04-claude-cli-reference.md`. Revalidate if the installed CLI version changes.
