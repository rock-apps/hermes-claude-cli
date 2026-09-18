# 09 — Scope and migration

What was kept vs. dropped from the two third-party projects this plugin replaces, and why. Details in [01](./01-analise-claude-bridge.md) and [02](./02-analise-hermes-claude-cli-original.md).

## Kept (with fixes)

| Feature | Origin | Change |
|---|---|---|
| `claude-cli` provider in the Hermes picker (`hermes model`) | original `hermes-claude-cli` | Same concept; `auth_type="external_process"` instead of an HTTP `base_url` + fake env var. |
| Friendly aliases (`claude`, `claude-code`, `claude-max`, `claude-subscription`) | original `hermes-claude-cli` | Kept as-is. |
| Model catalog (`sonnet`/`opus`/`haiku` + versioned IDs) | both | Kept; needs the same ongoing manual maintenance any Hermes provider requires as Anthropic ships new models. |
| Substring-based model alias normalization | `claude-bridge` | Ported into `protocol.py`. |
| Configurable read directories (`--add-dir`) | `claude-bridge` | Concept kept; the hardcoded personal-directory list was dropped (see [07](./07-configuracao.md)). |
| `stop_reason` → `finish_reason` mapping | `claude-bridge` | Ported as-is. |
| `default_aux_model="haiku"` | original `hermes-claude-cli` | Kept. |
| Cost/usage accounting | `claude-bridge` (advertised, but broken) | Actually fixed — real `total_cost_usd`/`usage` are parsed from `--output-format json`, not hardcoded to zero. |

## Out of scope (not replicated)

| Item | Origin | Why |
|---|---|---|
| Dedicated HTTP server (`cmd/claude-bridge/main.go`) | `claude-bridge` | Replaced by `create_client()`/direct subprocess — see [04](./04-decisao-bridge-e-necessario.md). |
| `model-router` / `zai-proxy` binaries (routing the Claude Code CLI itself to DeepSeek/z.ai) | `claude-bridge` | Solves a different problem (swapping *Claude Code's own* model backend, not integrating Claude into Hermes). Undocumented, unreferenced by the Hermes plugin, introduced via a stray "backup" commit. Scope creep — if this capability is ever wanted, it's a separate project. |
| Committed binaries/PID files | `claude-bridge` | Repo-hygiene mistake in the original; this project's `.gitignore` prevents it from the start. |
| systemd unit for the bridge | both | No long-running process to manage anymore. |
| Cloning a second repository during install | original `hermes-claude-cli` | Everything lives in one repository now. |
| `CLAUDE_BRIDGE_URL` as a fake credential for the provider picker | original `hermes-claude-cli` | `auth_type="external_process"` solves this natively. |
| Serving non-Hermes HTTP clients (Open WebUI, LibreChat, Cursor) | `claude-bridge` | Out of scope for a Hermes-only plugin. Tracked as an optional, undemanded Fase 6 in [10-roadmap.md](./10-roadmap.md). |
| `claude-agent-sdk` (Anthropic's official PyPI package, used by projects like [`RichardAtCT/claude-code-openai-wrapper`](https://github.com/RichardAtCT/claude-code-openai-wrapper)) as the basis for `process.py` | evaluated, not adopted | The SDK is async (`async for` in `query()`), which doesn't fit the synchronous pattern the reference `CopilotACPClient` uses (blocking subprocess) — adopting it would need an async bridge inside `create_client()` plus an extra dependency, for no real gain: the real `claude -p --output-format json` schema (see [06](./06-referencia-cli-claude.md)) is simple enough to parse with the stdlib alone. The cited wrapper solves the same problem as `claude-bridge` (exposes HTTP), just with the SDK instead of manual parsing — it doesn't change the decision in [04](./04-decisao-bridge-e-necessario.md). Session continuity (Fase 4) ended up implemented directly via `--session-id`/`--resume` without needing the SDK. |

## Persistent limitations (not solved by any architecture choice)

- **No passthrough for external `tools:` definitions** — a limitation of the `claude` CLI itself, not the transport (see [06](./06-referencia-cli-claude.md)).
- **Per-call subprocess overhead (~1–3s)** — inherent to the `claude` CLI, present in both the old and new architecture.
- **No native ACP protocol in the `claude` CLI** — the subprocess integration needs its own parser for `claude -p`'s output shape; it can't reuse the ACP parser Hermes already has for Copilot.
