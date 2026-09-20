# 02 — ADR: is an HTTP bridge necessary?

**Status**: accepted and implemented.

## The question, split in two

### Part 1 — is a translation layer necessary?

**Yes.** The `claude` CLI exposes no HTTP API; it's invoked via command line with stdin/stdout/argv. Hermes Agent, meanwhile, models every model provider as something that speaks a network `api_mode` (`chat_completions`, `anthropic_messages`, or `codex_responses`) — see [01](./01-hermes-provider-model.md). There's no "protocol-less generic provider" in Hermes — even the closest case (`copilot-acp`) still advertises `api_mode="chat_completions"` and implements a client class exposing `.chat.completions.create()`.

Conclusion: some translation layer between "a Hermes provider call" and "a `claude` CLI invocation" is mandatory. That responsibility can't be eliminated.

### Part 2 — does that layer need to be a separate HTTP server?

**No.** That's an implementation choice, not a Hermes requirement. Hermes already ships a first-class extension point, used in production by Nous Research itself, built for exactly "a provider whose protocol isn't HTTP":

```python
class ProviderProfile:
    auth_type: str = "api_key"  # ... or "external_process"
    def create_client(self, **client_kwargs) -> Any | None:
        """Return a custom client. None = use the standard OpenAI HTTP client."""
```

The bundled `copilot-acp` provider uses exactly this today, talking to the `copilot` binary over subprocess + stdio (the ACP/JSON-RPC protocol) — no HTTP server, port, or systemd process anywhere.

## Decision

This plugin runs no separate HTTP server. Instead:

1. It registers a `ProviderProfile` with `auth_type="external_process"` — the same pattern `copilot-acp` uses.
2. `create_client()` returns `ClaudeCLIClient`, exposing `.chat.completions.create(...)`.
3. Internally, `ClaudeCLIClient` invokes `claude -p --output-format json ...` as a subprocess **inside Hermes' own Python process** — no socket, no port, no separate daemon.
4. Message translation between OpenAI-shaped messages and `claude` CLI prompt/flags lives in this plugin's `protocol.py`.

## Consequences

### Positive

- **No network attack surface.** There's no listening port at all.
- **One repository, one language.** The whole plugin is Python, in the same process Hermes already runs.
- **No extra systemd process to keep alive, restart, or monitor.** The `claude` subprocess lives and dies with each call (or with a resumed session, see Fase 4 in [08-roadmap.md](./08-roadmap.md)), managed entirely by Hermes' own process lifecycle.
- **Access to real CLI capabilities**: real cost/usage accounting via `--output-format json`, session resume via `--resume`, and permission modes more granular than "bypass everything" — see [04](./04-claude-cli-reference.md) and [06](./06-security.md).
- **Simpler install.** No separate build step, no second repository, no systemd unit to edit.

### Trade-offs

- An HTTP bridge could be reused by tools outside Hermes. This plugin doesn't support that; if it's ever needed, it belongs as a separate, explicitly opt-in mode — see Fase 6 in [08-roadmap.md](./08-roadmap.md), not built preemptively.
- The subprocess still has per-call startup overhead (~1–3s) — a `claude` CLI limitation, not a transport one.
- This plugin depends on a Hermes-internal API (`ProviderProfile.create_client`, `auth_type="external_process"`) that, while documented and used in production, is part of an extremely fast-moving codebase and can change between Hermes versions — see [08-roadmap.md](./08-roadmap.md) for a real compatibility gap this surfaced (an older, previously-installed Hermes Agent version lacked this mechanism entirely).

## Alternative considered and rejected

**Keep an HTTP server, but embed it in the same process** (e.g. a Python `http.server` on a background thread, started by a plugin lifecycle hook) instead of a plain subprocess. Rejected because:

- Hermes has no documented "on plugin load, start a background service" hook to build that on.
- It would still carry the "unnecessary local port" problem.
- The `external_process` pattern is strictly better when Hermes is the only consumer, which is the case here.
