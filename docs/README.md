# Documentation — hermes-claude-cli

Recommended reading order:

| # | Document | Content |
|---|-----------|----------|
| 00 | [Overview](./00-overview.md) | Project goal and context |
| 03 | [How Hermes Agent handles providers](./03-hermes-provider-model.md) | Reverse-engineering of `NousResearch/hermes-agent`'s provider plugin mechanism (primary source, not third-party docs) |
| 04 | [Decision: is a bridge necessary?](./04-is-bridge-necessary.md) | The ADR behind this project's core architecture |
| 05 | [Unified architecture](./05-unified-architecture.md) | Design of the plugin |
| 06 | [Reference: relevant `claude` CLI flags](./06-claude-cli-reference.md) | The `claude` CLI flags this integration relies on |
| 07 | [Configuration](./07-configuration.md) | Environment variables and configuration surface |
| 08 | [Security](./08-security.md) | Threat model and mitigations |
| 09 | [Scope and migration](./09-scope-and-migration.md) | What was evaluated and rejected, and why |
| 10 | [Roadmap](./10-roadmap.md) | Implementation phases and current status |

Numbering starts at 00/03 — 01/02 were retired analysis notes on two now-unrelated third-party projects, removed once this plugin's own architecture stood on its own.

## Status

Implemented and validated end-to-end inside a real Hermes Agent installation. See [10-roadmap.md](./10-roadmap.md) for the phase-by-phase record and what remains open.
