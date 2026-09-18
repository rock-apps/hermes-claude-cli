# 00 — Overview

## What this project is

A single Hermes Agent plugin (this repository, `rock-apps/hermes-claude-cli`) that lets the Claude CLI (Claude Code), authenticated with a **Claude Max subscription**, act as a first-class model provider inside [Hermes Agent](https://github.com/NousResearch/hermes-agent) — without an HTTP bridge.

It replaces two third-party repositories that solved the same problem differently:

- [`niski84/claude-bridge`](https://github.com/niski84/claude-bridge) — a Go HTTP server exposing an OpenAI-compatible API (`/v1/chat/completions`) that shells out to the `claude` CLI behind it.
- [`niski84/hermes-claude-cli`](https://github.com/niski84/hermes-claude-cli) — a Python Hermes plugin registering a `claude-cli` provider that pointed at the `claude-bridge` above.

Goal shared with both: use a Claude Max subscription (via the authenticated `claude` CLI) as a first-class model provider in Hermes, avoiding the "extra usage" billing that direct API-key/OAuth access triggers.

## The question that shaped the architecture

> "What if that bridge isn't actually necessary? Analyze it."

Short answer (full reasoning in [ADR 04](./04-is-bridge-necessary.md)): the bridge's **function** — translating an OpenAI-compatible HTTP call into a `claude` CLI invocation — is necessary, because that's the only way to talk to a CLI tool. But the bridge's **implementation** in both third-party projects — a separate Go binary, in a separate repository, running as a systemd service, listening on an unauthenticated TCP port — is not. Hermes Agent already ships an extension point built for exactly this case: `ProviderProfile.create_client()` + `auth_type="external_process"`, the same mechanism its bundled `copilot-acp` provider uses. That lets the whole translation layer live inside this Python plugin as a local subprocess over stdio — no HTTP server, port, or systemd unit anywhere.

That's what got built, tested (81 passing tests), and validated end-to-end against a real Hermes Agent installation — see [10-roadmap.md](./10-roadmap.md) for the full record.

## Facts this project depends on

1. **"Hermes" is [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research)** — confirmed, not assumed: the plugin is built against its real `providers` API and has been run successfully inside a live Hermes Agent process, including the maintainer's own personal installation.
2. This repository is the single, definitive plugin — no dependency on cloning or maintaining `niski84/claude-bridge` or `niski84/hermes-claude-cli`.
3. The target environment has the **Claude Code CLI (`claude`)** installed and authenticated with a Max subscription — same prerequisite the third-party projects had.
4. The repository's software license is the one thing still undecided; everything else (package name, install method, permission defaults) was resolved during implementation — see [10-roadmap.md](./10-roadmap.md).

## How this was researched

Beyond reading READMEs: the full Go source of `claude-bridge` (including two undocumented binaries buried in a "backup" commit, `model-router` and `zai-proxy` — unrelated to this project, see [09](./09-scope-and-migration.md)); both repos' commit histories; the real Hermes Agent source (`providers/base.py`, `providers/__init__.py`, the bundled `copilot-acp` provider and its `agent/copilot_acp_client.py` client, and its official `adding-providers.md` developer doc); and the full `claude --help` output to find CLI capabilities (real streaming, session resume, permission modes) the original bridge never used.

That last source is what made the difference: neither third-party repo mentions `auth_type="external_process"`, because it was likely added to Hermes Agent for the Copilot provider around the same time or after `claude-bridge` was written.
