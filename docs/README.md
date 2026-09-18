# Documentation — hermes-claude-cli

Recommended reading order:

| # | Document | Content |
|---|-----------|----------|
| 00 | [Overview](./00-visao-geral.md) | Project goal, context, and the question that shaped the architecture |
| 01 | [Analysis: claude-bridge](./01-analise-claude-bridge.md) | Full reverse-engineering of `niski84/claude-bridge` |
| 02 | [Analysis: hermes-claude-cli (original)](./02-analise-hermes-claude-cli-original.md) | Full reverse-engineering of `niski84/hermes-claude-cli` |
| 03 | [How Hermes Agent handles providers](./03-modelo-de-provider-do-hermes.md) | Reverse-engineering of `NousResearch/hermes-agent`'s provider plugin mechanism (primary source, not third-party docs) |
| 04 | [Decision: is the bridge necessary?](./04-decisao-bridge-e-necessario.md) | The ADR behind this project's core architecture |
| 05 | [Unified architecture](./05-arquitetura-unificada.md) | Design of the single plugin that replaces both original repos |
| 06 | [Reference: relevant `claude` CLI flags](./06-referencia-cli-claude.md) | The `claude` CLI flags this integration relies on |
| 07 | [Configuration](./07-configuracao.md) | Environment variables and configuration surface |
| 08 | [Security](./08-seguranca.md) | Threat model and mitigations |
| 09 | [Scope and migration](./09-escopo-e-migracao.md) | What was kept, what was dropped (and why), from the two original repos |
| 10 | [Roadmap](./10-roadmap.md) | Implementation phases and current status |

## Status

Implemented and validated end-to-end inside a real Hermes Agent installation. See [10-roadmap.md](./10-roadmap.md) for the phase-by-phase record and what remains open.
