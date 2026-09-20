# 05 — Architecture

## Component diagram

```
┌───────────────────────────────────────────────────────────────────┐
│  Hermes Agent (user's Python process)                              │
│                                                                     │
│   hermes model  →  selects the "claude-cli" provider               │
│         │                                                          │
│         ▼                                                          │
│   providers.get_provider_profile("claude-cli")                     │
│         │                                                          │
│         ▼                                                          │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  $HERMES_HOME/plugins/model-providers/claude-cli/            │  │
│  │       → symlink (dev) or installed copy (end users) of       │  │
│  │         plugin/claude_cli/ from this repository               │  │
│  │                                                                │
│  │  ClaudeCLIProviderProfile(ProviderProfile)                    │  │
│  │    auth_type = "external_process"                             │  │
│  │    create_client() → ClaudeCLIClient(**kwargs)                │  │
│  │                                                                │
│  │  ClaudeCLIClient  (one instance per Hermes conversation)      │  │
│  │    .chat.completions.create(model, messages, stream, ...)     │  │
│  │      │                                                        │  │
│  │      ├─ protocol.py  → OpenAI messages ⇄ prompt/flags         │  │
│  │      ├─ session.py   → decides if this turn can --resume      │  │
│  │      └─ process.py   → subprocess.run(["claude", ...])        │  │
│  └───────────────────────┬───────────────────────────────────────┘  │
└──────────────────────────┼───────────────────────────────────────┘
                            │ stdio (argv + stdin/stdout, no network)
                            ▼
                    `claude` CLI (Anthropic's binary)
                            │ OAuth (~/.claude/.credentials.json)
                            ▼
                 Claude Max subscription (base plan allowance)
```

No network hop and no systemd process anywhere in this diagram — the `claude` subprocess runs inline inside Hermes' own process.

## Module layout (`plugin/claude_cli/`)

```
plugin/claude_cli/
├── plugin.yaml    # manifest (name, kind: model-provider, version, description, author)
├── __init__.py    # registers ClaudeCLIProviderProfile via register_provider()
├── client.py      # ClaudeCLIClient — implements create_client(), orchestrates a turn
├── protocol.py     # pure functions: OpenAI messages ⇄ prompt/flags translation
├── process.py      # subprocess spawn/parse, subprocess env allowlist
├── session.py       # pure logic: can this turn safely --resume the last one?
├── config.py        # environment variable resolution (see docs/07)
└── models.py         # static model alias/catalog
```

Each module has one responsibility: `client.py` doesn't know how to build CLI argv, `protocol.py` doesn't know how to spawn a subprocess, `process.py` doesn't know the OpenAI message shape, `session.py` has no I/O at all (pure functions, easy to unit test).

## Responsibilities, module by module

### `__init__.py`

```python
class ClaudeCLIProviderProfile(ProviderProfile):
    def create_client(self, **client_kwargs):
        return ClaudeCLIClient(**client_kwargs)

claude_cli = ClaudeCLIProviderProfile(
    name="claude-cli",
    aliases=("claude", "claude-code", "claude-max", "claude-subscription"),
    display_name="Claude CLI (Max subscription)",
    auth_type="external_process",
    base_url="process://claude-cli",       # symbolic, never used for real networking
    process_command="claude",
    process_command_env_vars=("CLAUDE_CLI_BIN", "CLAUDE_BIN"),
    fallback_models=FALLBACK_MODELS,        # from models.py
    default_aux_model=DEFAULT_AUX_MODEL,
    supports_model_listing=False,           # no /models endpoint — uses fallback_models
)
register_provider(claude_cli)
```

The `providers`/`providers.base` imports are guarded with `try/except ImportError`, so this module is a safe no-op outside a real Hermes process (e.g. this project's own test suite).

### `client.py` — `ClaudeCLIClient`

Mirrors `CopilotACPClient`'s minimal surface (see [01](./01-hermes-provider-model.md)):
- `.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create_chat_completion))`
- `HERMES_SKIP_TRANSPORT_WRAP = True` — tells Hermes not to re-wrap this client in its generic HTTP transport.
- `close()` is a no-op (Hermes calls it unconditionally on cleanup; each call here is already self-contained).
- `_effective_timeout()` normalizes Hermes' `timeout` argument, which can be either a bare float or an `httpx.Timeout`-like object (`.read`/`.write`/`.connect`/`.pool`) — confirmed empirically against a real Hermes process, not assumed.
- `_run_turn()` (non-streaming) and `_run_turn_streaming()` (streaming) both build on `_decide_call()`, which asks `session.compute_delta()` whether the current call can safely `--resume` the previous one tracked on `self`, and `_record_result()`, which updates that tracked state after every successful call — one shared decision, two execution paths (`run_once` vs `run_streaming`).
- `stream=True` calls `_run_turn_streaming()` (a generator) and converts its `StreamChunk`s directly into `.choices[i].delta.content` / `.delta.reasoning_content` chunks via `_stream_openai_chunks()` — see the streaming note below.

### `protocol.py`

Pure translation functions, no I/O: `flatten_messages()` (system prompt + transcript + current message, flattened into the single prompt string `claude -p` expects), `normalize_model_alias()` (collapses a full model ID to a bare alias when it matches `sonnet`/`opus`/`haiku`), `map_stop_reason()` (`claude`'s `stop_reason` → an OpenAI `finish_reason`).

### `process.py`

`build_args()` builds the CLI argv (always ends with `-- <prompt>`, a deliberate separator — `--add-dir` is variadic and would otherwise swallow a prompt that doesn't start with `-`, see [06-security.md](./06-security.md)). `run_once()` runs `claude` via `subprocess.run(..., check=False)` and always tries `json.loads()` on stdout first, regardless of exit code — the CLI reports its own API-level errors (bad model, etc.) inside a well-formed JSON payload with `is_error: true`, not via a non-JSON crash. `run_streaming()` does the streaming equivalent over a `Popen` pipe, one JSON event per line — see the streaming note below. `build_subprocess_env()` is the allowlist described in [06-security.md](./06-security.md).

### `session.py`

`compute_delta(previous_messages, current_messages)` — pure function, no subprocess/I/O. Returns the messages appended since the last tracked call, or `None` when continuity can't be trusted (history rewritten/compacted, shorter than before, or nothing tracked yet). `client.py` uses `None` as the signal to fall back to a normal full-history call.

## Streaming: what's actually implemented

`stream=True` delivers real incremental text via `process.run_streaming()`, which runs `claude` with `--output-format stream-json --include-partial-messages --verbose` and yields a `StreamChunk` per `content_block_delta` event (`text_delta` → `StreamChunk.text_delta`, `thinking_delta` on extended-thinking models → `StreamChunk.reasoning_delta`), plus one final chunk carrying the same `CLIResult` a non-streaming call would get. This was initially skipped — Hermes' own bundled `copilot_acp_client.py` reference doesn't do real incremental streaming for its subprocess provider either, so `stream=True` first just replayed one finished completion as a single fake chunk — but got built after all once real usage showed the cost of that shortcut (Hermes' UI shows "no stream output" with zero feedback for the entire duration of a `claude` call, indistinguishable from a hang). See Fase 2 in [08-roadmap.md](./08-roadmap.md) for the full story, including a real `--verbose`-requirement bug caught while building this.

## No `scripts/reload.sh` / systemd equivalent, and why

There's no long-running process to restart. The `claude` "process" is spawned and destroyed per call (or reused across a resumed session's lifetime — still no persistent process, just a resumable id), inside Hermes' own process lifecycle — no zombie processes, port conflicts, or restart-after-crash to manage.

## Install paths

Two, documented in the top-level README: `hermes plugins install rock-apps/hermes-claude-cli/plugin/claude_cli --enable` (one command, no manual clone — recommended for using the plugin) and clone + `scripts/install.sh` (symlinks `plugin/claude_cli/`, recommended for developing it, since local edits apply immediately). No build step, no additional binary, no systemd unit in either case.
