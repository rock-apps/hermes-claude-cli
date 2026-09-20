# Documentation — hermes-claude-cli

Recommended reading order:

| # | Document | Content |
|---|-----------|----------|
| 00 | [Overview](./00-overview.md) | Project goal and context |
| 01 | [How Hermes Agent handles providers](./01-hermes-provider-model.md) | Reverse-engineering of `NousResearch/hermes-agent`'s provider plugin mechanism (primary source, not third-party docs) |
| 02 | [Decision: is a bridge necessary?](./02-is-bridge-necessary.md) | The ADR behind this project's core architecture |
| 03 | [Unified architecture](./03-unified-architecture.md) | Design of the plugin |
| 04 | [Reference: relevant `claude` CLI flags](./04-claude-cli-reference.md) | The `claude` CLI flags this integration relies on |
| 05 | [Configuration](./05-configuration.md) | Environment variables and configuration surface |
| 06 | [Security](./06-security.md) | Threat model and mitigations |
| 07 | [Scope and migration](./07-scope-and-migration.md) | What was evaluated and rejected, and why |
| 08 | [Roadmap](./08-roadmap.md) | Implementation phases and current status |

See also [`../mcp-bridge/README.md`](../mcp-bridge/README.md) for the MCP bridge that gives `claude-cli` access to Hermes' native cron/kanban tools.

## Status

Implemented and validated end-to-end inside real Hermes Agent installations, including production. See [08-roadmap.md](./08-roadmap.md) for the phase-by-phase record and what remains open.
