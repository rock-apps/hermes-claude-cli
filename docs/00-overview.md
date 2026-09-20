# 00 — Overview

## What this project is

A Hermes Agent plugin (`rock-apps/hermes-claude-cli`) that lets the Claude CLI (Claude Code), authenticated with a **Claude Max subscription**, act as a first-class model provider inside [Hermes Agent](https://github.com/NousResearch/hermes-agent) — without an HTTP bridge.

Goal: use a Claude Max subscription (via the authenticated `claude` CLI) as a first-class model provider in Hermes, avoiding the "extra usage" billing that direct API-key/OAuth access triggers.

## The architecture decision

Talking to a CLI tool from Hermes needs some translation layer between an OpenAI-compatible request and a `claude` CLI invocation. The question was whether that layer needs to be a separate HTTP server (its own repository, a systemd service, a listening port) — full reasoning in [ADR 02](./02-is-bridge-necessary.md).

It doesn't: Hermes Agent ships an extension point built for exactly this case — `ProviderProfile.create_client()` + `auth_type="external_process"`, the same mechanism its bundled `copilot-acp` provider uses. That lets the whole translation layer live inside this Python plugin as a local subprocess over stdio — no HTTP server, port, or systemd unit anywhere.

That's what got built, tested, and validated end-to-end against a real Hermes Agent installation — see [08-roadmap.md](./08-roadmap.md) for the full record.

## Facts this project depends on

1. **"Hermes" is [Hermes Agent](https://github.com/NousResearch/hermes-agent) (Nous Research)** — confirmed, not assumed: the plugin is built against its real `providers` API and has been run successfully inside a live Hermes Agent process, including the maintainer's own personal installation.
2. The target environment has the **Claude Code CLI (`claude`)** installed and authenticated with a Max subscription.
3. The repository's software license is the one thing still undecided; everything else (package name, install method, permission defaults) was resolved during implementation — see [08-roadmap.md](./08-roadmap.md).

## How this was researched

The real Hermes Agent source (`providers/base.py`, `providers/__init__.py`, the bundled `copilot-acp` provider and its `agent/copilot_acp_client.py` client, and its official `adding-providers.md` developer doc), and the full `claude --help` output to find CLI capabilities (real streaming, session resume, permission modes) — verified empirically against a real installed `claude` CLI rather than assumed from documentation.
