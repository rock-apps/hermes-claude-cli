# 09 — Scope and migration

What was kept vs. dropped from the two third-party projects this plugin replaces, and why. Details in [01](./01-analysis-claude-bridge.md) and [02](./02-analysis-hermes-claude-cli-original.md).

## Kept (with fixes)

| Feature | Origin | Change |
|---|---|---|
| `claude-cli` provider in the Hermes picker (`hermes model`) | original `hermes-claude-cli` | Same concept; `auth_type="external_process"` instead of an HTTP `base_url` + fake env var. |
| Friendly aliases (`claude`, `claude-code`, `claude-max`, `claude-subscription`) | original `hermes-claude-cli` | Kept as-is. |
| Model catalog (`sonnet`/`opus`/`haiku` + versioned IDs) | both | Kept; needs the same ongoing manual maintenance any Hermes provider requires as Anthropic ships new models. |
| Substring-based model alias normalization | `claude-bridge` | Ported into `protocol.py`. |
| Configurable read directories (`--add-dir`) | `claude-bridge` | Concept kept; the hardcoded personal-directory list was dropped (see [07](./07-configuration.md)). |
| `stop_reason` → `finish_reason` mapping | `claude-bridge` | Ported as-is. |
| `default_aux_model="haiku"` | original `hermes-claude-cli` | Kept. |
| Cost/usage accounting | `claude-bridge` (advertised, but broken) | Actually fixed — real `total_cost_usd`/`usage` are parsed from `--output-format json`, not hardcoded to zero. |

## Out of scope (not replicated)

| Item | Origin | Why |
|---|---|---|
| Dedicated HTTP server (`cmd/claude-bridge/main.go`) | `claude-bridge` | Replaced by `create_client()`/direct subprocess — see [04](./04-is-bridge-necessary.md). |
| `model-router` / `zai-proxy` binaries (routing the Claude Code CLI itself to DeepSeek/z.ai) | `claude-bridge` | Solves a different problem (swapping *Claude Code's own* model backend, not integrating Claude into Hermes). Undocumented, unreferenced by the Hermes plugin, introduced via a stray "backup" commit. Scope creep — if this capability is ever wanted, it's a separate project. |
| Committed binaries/PID files | `claude-bridge` | Repo-hygiene mistake in the original; this project's `.gitignore` prevents it from the start. |
| systemd unit for the bridge | both | No long-running process to manage anymore. |
| Cloning a second repository during install | original `hermes-claude-cli` | Everything lives in one repository now. |
| `CLAUDE_BRIDGE_URL` as a fake credential for the provider picker | original `hermes-claude-cli` | `auth_type="external_process"` solves this natively. |
| Serving non-Hermes HTTP clients (Open WebUI, LibreChat, Cursor) | `claude-bridge` | Out of scope for a Hermes-only plugin. Tracked as an optional, undemanded Fase 6 in [10-roadmap.md](./10-roadmap.md). |
| `claude-agent-sdk` (Anthropic's official PyPI package, used by projects like [`RichardAtCT/claude-code-openai-wrapper`](https://github.com/RichardAtCT/claude-code-openai-wrapper)) as the basis for `process.py` | evaluated twice, not adopted | First pass: the SDK is async (`async for` in `query()`), which doesn't fit the synchronous pattern the reference `CopilotACPClient` uses (blocking subprocess) — adopting it would need an async bridge inside `create_client()` plus an extra dependency, for no real gain: the real `claude -p --output-format json` schema (see [06](./06-claude-cli-reference.md)) is simple enough to parse with the stdlib alone. The cited wrapper solves the same problem as `claude-bridge` (exposes HTTP), just with the SDK instead of manual parsing — it doesn't change the decision in [04](./04-is-bridge-necessary.md). Session continuity (Fase 4) ended up implemented directly via `--session-id`/`--resume` without needing the SDK. **Second pass (re-evaluated after hitting the `tools:` passthrough limitation below in real production use — see [06](./06-claude-cli-reference.md)):** the Agent SDK *does* support custom tool schemas (MCP servers, `allowedTools`), which would fix that limitation — but per Anthropic's own docs (`code.claude.com/docs/en/agent-sdk/quickstart.md`, `.../authentication.md`), the Agent SDK requires `ANTHROPIC_API_KEY` (or a cloud provider: Bedrock/Vertex/Foundry) and explicitly does not support reusing a Claude Max subscription's local OAuth session (`~/.claude/.credentials.json`) — that credential chain is documented as CLI-only. Anthropic states directly: "Unless previously approved, Anthropic does not allow third party developers to offer claude.ai login or rate limits for their products, including agents built on the Claude Agent SDK." Switching to the Agent SDK would trade the entire reason this project exists (billing against the Max plan's base allowance, not per-token API credits) for custom-tool support. Rejected for the same reason a second time, now with the tradeoff fully quantified: **there is no path to both** with Anthropic's current SDK design. **Third pass — correction after reading the SDK's actual source (not just its docs):** `anthropics/claude-agent-sdk-python`, `src/claude_agent_sdk/_internal/transport/subprocess_cli.py`, resolves the backend via `shutil.which("claude")` and spawns it with `inherited_env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}` — i.e. the SDK's default transport is itself a wrapper around the same local `claude` CLI binary this plugin already shells out to, inheriting the full calling environment. Read literally, that means a locally-authenticated Max OAuth session (`~/.claude/.credentials.json`) would be picked up the same way it is by this plugin, *if* `ANTHROPIC_API_KEY` is left unset — so the SDK-requires-API-key claim in the docs is a **stated policy**, not a **hard technical block enforced in this code path**. This doesn't reverse the second-pass rejection (Anthropic's terms explicitly disallow this for anything resembling a distributed product, "Unless previously approved..."), but the previous entry overstated it as a pure technical impossibility — it's a ToS/policy risk being evaluated, not a wall. Not verified end-to-end (no test run against a real Max session with `ANTHROPIC_API_KEY` unset); if this is ever revisited, that's the first thing to actually run, not infer. |

## Persistent limitations (not solved by any architecture choice)

- **No passthrough for external `tools:` definitions** — a limitation of the `claude` CLI itself, not the transport (see [06](./06-claude-cli-reference.md)).
- **Per-call subprocess overhead (~1–3s)** — inherent to the `claude` CLI, present in both the old and new architecture.
- **No native ACP protocol in the `claude` CLI** — the subprocess integration needs its own parser for `claude -p`'s output shape; it can't reuse the ACP parser Hermes already has for Copilot.

## Open question, not investigated further: a "Hermes MCP bridge" for `claude-cli`

Raised in discussion, not built, not validated — recorded so a future session doesn't have to re-derive it from scratch.

The `tools:` passthrough limitation (above) is about *per-request* tool schemas — Hermes can't hand the model a dynamic `tools:` array on `claude -p`. But the `claude` CLI separately supports **persistently configured MCP servers** (`claude mcp add <name> -- <cmd>`, or a project/global `.mcp.json`), which *do* become part of the model's known toolset for every invocation, no per-request injection needed. This is almost certainly how Sharp/TLE MCP-backed Slack lookups worked correctly through `claude-cli` in real usage on the `muse` deployment (see [06](./06-claude-cli-reference.md)) even though Hermes-native tools (`cronjob_manage`, `delegate_task`, `kanban_create`/`kanban_show`/`kanban_complete`) did not — the former are (presumably) configured as MCP servers the `claude` CLI already knows about independent of Hermes; the latter only exist as Hermes-internal Python functions exposed exclusively via the per-request `tools:` array.

The unexplored idea: build a small MCP server that wraps Hermes' own native tool-calling internals (cron, kanban, delegate_task) and register it with the `claude` CLI via `claude mcp add`. If that works, a `claude-cli`-backed profile could gain access to Hermes-native tools **without any per-request passthrough and without leaving the Max-subscription auth path** — because MCP server configuration is orthogonal to the OAuth-vs-API-key question this whole document is about.

Not evaluated: whether Hermes' internal tool implementations are cleanly separable from its own request/agent-loop machinery enough to be re-exposed as a standalone MCP server, how much duplicate logic that would require, and whether Hermes' own dispatcher/kanban semantics (atomic claims, workspace isolation, durability) would even make sense invoked from outside Hermes' own process. Worth a real spike before assuming it's viable — it is *not* confirmed to work, only structurally plausible from reading `claude --help`'s `mcp` subcommands and observing that MCP-backed lookups already work through `claude-cli` in practice.
