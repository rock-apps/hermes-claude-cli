# 03 — How Hermes Agent actually handles providers

Source: real [`NousResearch/hermes-agent`](https://github.com/NousResearch/hermes-agent) code (`providers/base.py`, `providers/__init__.py`, `plugins/model-providers/copilot-acp/`, `agent/copilot_acp_client.py`, `website/docs/developer-guide/adding-providers.md`) — not third-party documentation. This is the piece of research the two original projects didn't have (or didn't apply).

## Plugin discovery

`providers/__init__.py::_discover_providers()` scans, on the first call to `get_provider_profile()` or `list_providers()`:

1. `plugins/model-providers/<name>/` — bundled with Hermes Agent itself.
2. `$HERMES_HOME/plugins/model-providers/<name>/` — user plugins (this is where this plugin installs, same convention the original `claude-cli` used).
3. (optional, opt-in) `pip` packages declaring a `hermes_agent.plugins` entry point.

Each directory needs `__init__.py` (calls `register_provider(profile)` at module level) plus `plugin.yaml` (manifest: `name`, `kind: model-provider`, `version`, `description`, `author`). User plugins override bundled ones with the same name (last-writer-wins).

## The core abstraction: `ProviderProfile` (dataclass, `providers/base.py`)

- `api_mode: str = "chat_completions"` — how the transport formats the request. Other values in the source: `anthropic_messages` (Hermes' native `anthropic` provider), `codex_responses` (OpenAI Codex, xAI Grok, Meta/Muse Spark, Ramp Router).
- `auth_type: str = "api_key"` — other values: `oauth_device_code`, `oauth_external`, `copilot`, `aws_sdk`, and **`external_process`**.
- `base_url: str` — required for the standard HTTP path.
- **Fields specific to `auth_type="external_process"`**: `process_command`, `process_args`, `process_command_env_vars`, `process_args_env_var` — "An agent CLI driven over stdio (ACP) rather than an HTTP endpoint" (literal source comment).
- **`create_client(self, **client_kwargs) -> Any | None`** — hook that returns `None` by default (the core builds the standard `openai.OpenAI` client pointed at `base_url`). A subclass can override it and return *any* object implementing the minimal interface the rest of Hermes expects (`.chat.completions.create(...)`), including one that makes no network calls at all. Literal docstring:

  > "This is the hook that lets a provider ship *outside* this tree: with it, a profile registered from `~/.hermes/plugins/model-providers/` or a pip entry point can supply its own transport without any core edit. See `plugins/model-providers/copilot-acp/` for the in-tree example."

Hermes Agent's own source documents this as the intended mechanism for exactly this use case.

## Existing production proof of concept: `copilot-acp`

`plugins/model-providers/copilot-acp/__init__.py` (bundled, maintained by Nous Research):

```python
class CopilotACPProfile(ProviderProfile):
    def create_client(self, **client_kwargs):
        from agent.copilot_acp_client import CopilotACPClient
        return CopilotACPClient(**client_kwargs)

copilot_acp = CopilotACPProfile(
    name="copilot-acp",
    api_mode="chat_completions",       # transport treats it as chat_completions
    base_url="acp://copilot",          # symbolic URL, never used for real HTTP
    auth_type="external_process",
    process_command="copilot",
    process_args=("--acp", "--stdio"),
    process_command_env_vars=("HERMES_COPILOT_ACP_COMMAND", "COPILOT_CLI_PATH"),
    process_args_env_var="HERMES_COPILOT_ACP_ARGS",
)
register_provider(copilot_acp)
```

`agent/copilot_acp_client.py` (476 lines) implements `CopilotACPClient`, which:

- Exposes `.chat.completions.create(...)` (via `SimpleNamespace`) — the same surface the real `openai` SDK would, so the rest of Hermes (`run_agent.py`) doesn't need to know it isn't HTTP.
- Internally runs `subprocess.Popen([...], stdin=PIPE, stdout=PIPE, stderr=PIPE)` on the `copilot --acp --stdio` binary and speaks **JSON-RPC 2.0 over stdio** (the ACP — Agent Client Protocol) directly, with dedicated threads reading stdout/stderr without blocking.
- Declares `HERMES_SKIP_TRANSPORT_WRAP = True` and `HERMES_SKIP_ASYNC_WRAP = True` — telling the core this client is already "complete" and shouldn't be re-wrapped by the generic HTTP transport layer.
- Implements timeouts, a compatibility probe (`_acp_supported`) to fail fast if the binary doesn't support the protocol, file-permission handling (`_ensure_path_within_cwd`, denies paths outside the session `cwd`), and content redaction (`redact_sensitive_text`) before returning file content read during the ACP session.

This is the reference pattern this plugin follows — not because the `claude` CLI speaks the same ACP protocol (it doesn't, see [06](./06-claude-cli-reference.md)), but because the *class of solution* (`create_client()` + `auth_type="external_process"` + a client class that talks to a subprocess over stdio) is exactly the gap an HTTP bridge would otherwise fill, more heavily and less safely.

## Alternative distribution: `pip` entry point

`providers/__init__.py::_discover_entry_point_providers()` also supports plugins distributed as a normal `pip` package:

```toml
[project.entry-points."hermes_agent.plugins"]
claude-cli = "hermes_claude_cli:register"
```

With one caveat: it's opt-in — only entry points whose name is in Hermes' `plugins.enabled` config get loaded. This plugin uses the directory/symlink path instead (no added friction), matching how it's installed today; the entry point remains a possible future distribution option, tracked as low priority in [10-roadmap.md](./10-roadmap.md).

## What this means for the wire protocol

Hermes stores conversation history internally in the **OpenAI chat-completions** shape (`role`/`content` messages, `tool_calls` with stringified `function.arguments`, `role: "tool"` messages). That's true regardless of transport — even `CopilotACPClient`, which doesn't speak HTTP, receives `messages` in the OpenAI shape and translates internally to its backend's native protocol. So removing the HTTP server doesn't remove the need for a message-translation layer — it just moves that layer inside the Hermes process, as plain Python, instead of a separate network service.
