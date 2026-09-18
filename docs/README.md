# Documentation — hermes-claude-cli

Recommended reading order:

| # | Document | Content |
|---|-----------|----------|
| 00 | [Overview](./00-overview.md) | Project goal, context, and the question that shaped the architecture |
| 01 | [Analysis: claude-bridge](./01-analysis-claude-bridge.md) | Full reverse-engineering of `niski84/claude-bridge` |
| 02 | [Analysis: hermes-claude-cli (original)](./02-analysis-hermes-claude-cli-original.md) | Full reverse-engineering of `niski84/hermes-claude-cli` |
| 03 | [How Hermes Agent handles providers](./03-hermes-provider-model.md) | Reverse-engineering of `NousResearch/hermes-agent`'s provider plugin mechanism (primary source, not third-party docs) |
| 04 | [Decision: is the bridge necessary?](./04-is-bridge-necessary.md) | The ADR behind this project's core architecture |
| 05 | [Unified architecture](./05-unified-architecture.md) | Design of the single plugin that replaces both original repos |
| 06 | [Reference: relevant `claude` CLI flags](./06-claude-cli-reference.md) | The `claude` CLI flags this integration relies on |
| 07 | [Configuration](./07-configuration.md) | Environment variables and configuration surface |
| 08 | [Security](./08-security.md) | Threat model and mitigations |
| 09 | [Scope and migration](./09-scope-and-migration.md) | What was kept, what was dropped (and why), from the two original repos |
| 10 | [Roadmap](./10-roadmap.md) | Implementation phases and current status |

## Status

Implemented and validated end-to-end inside a real Hermes Agent installation. See [10-roadmap.md](./10-roadmap.md) for the phase-by-phase record and what remains open.
