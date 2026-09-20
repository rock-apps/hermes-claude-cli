# 10 — Roadmap

## Status

Implemented and validated end-to-end: Fases 1 through 5 are all done. 94 tests passing, `ruff` clean.

Fase 2 (real streaming) was initially skipped, then built after all — see below for why the original "not worth it" call got revisited.

## Minimum Hermes Agent version

This plugin needs `ProviderProfile.create_client()` plus the `process_command`/`process_args`/`process_command_env_vars`/`process_args_env_var` fields in `providers/base.py`. Older Hermes Agent checkouts don't have this generic mechanism — they dispatch `copilot-acp` (the reference provider) via a hardcoded name/`base_url` check in `agent/agent_runtime_helpers.py` instead of a hook. Symptom on an incompatible version:

```
Failed to load user provider plugin claude-cli: ProviderProfile.__init__() got an unexpected keyword argument 'process_command'
```

Quick check in any Hermes checkout: `grep process_command providers/base.py` (present = compatible). Fix: `hermes update`. This is a genuine version-compatibility gap this project surfaced, not a plugin bug — this is an extremely fast-moving monorepo (tens of thousands of commits can separate two clones taken hours apart).

`hermes update` was run against the maintainer's own real, previously-installed Hermes Agent (with authorization) and pulled ~37,000 commits. It surfaced two issues unrelated to this plugin, left for the maintainer to resolve on their own schedule: an uncommitted local change to `hermes_cli/web_server.py` that conflicted on merge and is preserved unapplied in `git stash@{0}` (`cd ~/.hermes/hermes-agent && git stash show -p stash@{0}` to review), and an `npm` version mismatch that breaks only the Hermes dashboard/TUI build (core CLI unaffected). The plugin itself was confirmed working end-to-end post-update.

Also discovered post-update: recent Hermes versions install "portable" plugins (ones with a `plugin.yaml`, like this one) disabled by default as a security gate. `scripts/install.sh` now runs `hermes plugins enable claude-cli-provider` automatically (a no-op on older Hermes versions without that gate).

## Real end-to-end validation

Beyond the 81 unit tests (which never call the real `claude` CLI), this plugin was validated against real, live Hermes Agent processes multiple times: a fresh `main` clone in an isolated sandbox, the maintainer's own personal Hermes install (before and after `hermes update`), and via `hermes plugins install` from the published repository. Example, from a fresh clone:

```
$ python -m hermes_cli.main -z "What is the capital of Portugal? One word." --provider claude-cli -m sonnet
Lisboa
```

That proves Hermes' real provider-discovery mechanism finds this plugin and routes a real call through it — not just that `ClaudeCLIClient` works when called directly by this project's own tests.

Two real bugs only surfaced this way (Hermes calls the client differently than assumed):

1. **Timeout type**: Hermes passes `timeout` as an `httpx.Timeout`-like object (`.read`/`.write`/`.connect`/`.pool`), not a bare `float` — broke `subprocess.run(timeout=...)`. Fixed with `_effective_timeout()` in `client.py` (same fix shape as the reference `copilot_acp_client.py`).
2. **Streaming shape**: Hermes' internal relay always calls in streaming mode and expects chunks with `.choices[i].delta`, not a full `.choices[i].message`. Originally fixed by reusing the reference `copilot-acp` client's `agent.acp_openai_bridge.completion_to_stream_chunks(completion)` helper (one fake chunk from a finished completion); superseded once Fase 2 built real incremental chunks directly — see below.

A no-op `close()` was also added (Hermes calls it unconditionally during provider-client cleanup).

## What shipped, by phase

**Fase 0 (pre-implementation decisions)** — all resolved except the repository license (still no `LICENSE` file, undecided).

**Fase 1 — functional provider parity.** `plugin/claude_cli/{protocol,process,config,client,models,__init__}.py`. Real `--output-format json` parsing (`total_cost_usd`/`usage`/`session_id`/`is_error`). CLI JSON schema verified empirically against a real installed `claude` CLI (v2.1.276), not assumed.

**Fase 2 — real token streaming — built after all.** Originally skipped: Hermes' own `copilot_acp_client.py` reference doesn't do real incremental streaming either, so `stream=True` just replayed one finished completion as a single fake chunk. Revisited after real usage on a personal deployment surfaced the actual cost of that choice: with no incremental output, Hermes' UI shows "waiting on sonnet — no stream output for Ns" for the entire duration of a `claude` call (which can be long — extended thinking on a hard prompt easily exceeds a minute) with zero feedback, indistinguishable from a hang.

Implemented: `process.run_streaming()` runs `claude` with `--output-format stream-json --include-partial-messages` (verified empirically that `--print` + `stream-json` also requires `--verbose`, undocumented in `claude --help`'s flag description — a real bug caught before it shipped) and yields a `StreamChunk` per `content_block_delta` event — `text_delta` for normal output, `thinking_delta` for extended-thinking models — plus one final chunk carrying the same `CLIResult` shape `run_once` returns, parsed from the terminal `type: "result"` event. `client.py`'s `_stream_openai_chunks()` converts these directly into `.choices[i].delta.content` / `.delta.reasoning_content` chunks — no more detour through Hermes' `completion_to_stream_chunks` helper.

Session continuity (Fase 4) composes with this correctly: `_run_turn_streaming()` shares the same resume/fresh decision as the non-streaming path. One real behavioral difference found while wiring this up: an unknown `--resume` target in streaming mode does **not** raise (unlike `run_once`, which gets empty/unparseable stdout) — it comes back as a normal terminal chunk with `is_error=True`. Handled by retrying fresh transparently whenever nothing has been yielded to the caller yet (same user-visible behavior as the non-streaming fallback); if content was already streamed before the failure, the stream just ends rather than risking duplicated output from an invisible retry.

Real E2E proof (no mocks): incremental text deltas received one at a time via a live `ClaudeCLIClient.chat.completions.create(stream=True)` call, and a full two-turn session-continuity + streaming conversation (turn 1 "my favorite number is 12"; turn 2, streamed, resumed, only the delta sent → "15"). 13 new tests (`TestRunStreaming` in `test_process.py`, 4 new streaming tests in `test_client.py` replacing the now-obsolete `completion_to_stream_chunks` mock test), suite at 94, `ruff` clean.

**Fase 3 — security hardening.**
- Permission mode and `--restricted` defaults resolved (see [06-security.md](./06-security.md)).
- Subprocess environment allowlist (`process.build_subprocess_env()`): only `HOME`, `PATH`, `LANG`/`LC_*`, `TERM`, `TMPDIR`, `USER`, `LOGNAME`, `SHELL` pass through. Found in the process: a leaked `ANTHROPIC_API_KEY` silently overrides OAuth/Max auth and makes the CLI try to bill against that key instead — confirmed empirically, this is why the filter is an allowlist rather than a blocklist.
- Sensitive-content redaction: evaluated and deliberately not implemented — see [06-security.md](./06-security.md) for why.
- Real bug found and fixed: `--add-dir` is a variadic CLI flag; without a `--` separator, a prompt not starting with `-` was silently swallowed as one more directory whenever `CLAUDE_CLI_ALLOWED_DIRS` was set, failing with "Input must be provided...". Fixed by always inserting `--` before the prompt.
- Open: no default cap for `--max-budget-usd` (unset = unlimited) — a posture choice, not a bug.

**Fase 4 — session continuity, via `--resume`.** Investigated first (does Hermes reuse one `ClaudeCLIClient` instance across a conversation's turns, or build a new one each time?) by reading `agent/agent_runtime_helpers.py` in a fresh Hermes clone: it caches and reuses a client instance across sequential calls as long as construction kwargs don't change, only creating a fresh one for a genuinely concurrent call (which starts with no state — already the safe fallback wanted). Conclusion: per-instance state is safe.

Implemented: `plugin/claude_cli/session.py::compute_delta()` (pure function — returns the messages new since the last call, or `None` when continuity can't be trusted, e.g. a shorter or rewritten/compacted history). `ClaudeCLIClient` tracks `_last_messages`/`_last_session_id`/`_last_model` per instance behind a `threading.Lock`. `process.build_args()` gained `resume_session_id` (adds `--resume`, skips re-sending the system prompt since the CLI snapshots and replays it automatically on resume). Any `--resume` failure, or an `is_error=true` result, clears tracked state and falls back to a fresh full-history call automatically. New config: `CLAUDE_CLI_SESSION_CONTINUITY` (default `true`).

Empirical findings that shaped this: `--resume <valid-id>` plus a prompt containing only the new message works correctly (verified: turn 1 "my favorite number is 9"; turn 2 via `--resume` with only the new question → "10"). `--resume <unknown-id>` does **not** come back as an `is_error: true` JSON result the way an API error (e.g. bad model) does — it returns empty stdout and the error on stderr ("No conversation found with session ID: ..."), exit code 1, so `run_once()` raises `ClaudeCLIProcessError` there rather than returning a `CLIResult` — that's the exception `client.py`'s fallback actually catches.

Deliberately out of scope: no cross-process persistence (tracking is per-`ClaudeCLIClient` instance, so it doesn't survive a Hermes process restart or separate `hermes -z ...` invocations — acceptable, since the benefit already applies to long-lived conversations inside one long-running Hermes process, the common case). Real concurrent-call racing on the same instance wasn't tested against an actual race (the lock protects the read-decide-write sequence, but the CLI's own behavior under real concurrency on the same session isn't documented or verified) — not expected to occur given how Hermes manages its own client slots.

**Fase 5 — packaging and distribution.**
- `scripts/install.sh`: symlinks `plugin/claude_cli/` into `$HERMES_HOME/plugins/model-providers/claude-cli`. No second repository, no build step, no systemd. This is the recommended flow for developing the plugin (local edits apply immediately).
- One-command install for end users: `hermes plugins install <owner>/<repo>/<subdir>` already exists natively in Hermes and solves "install without a manual clone" — no custom `pyproject.toml`/entry point needed. Repository published at `github.com/rock-apps/hermes-claude-cli` (public) to make this usable: `hermes plugins install rock-apps/hermes-claude-cli/plugin/claude_cli --enable`.
  - Point at the `plugin/claude_cli` subdirectory, not the repo root — pointing at the root gets blocked by Hermes' built-in install-time security scanner (`plugins.scan_on_install`), which flagged a CAUTION verdict with 27 findings, almost all false positives from this repo's own `docs/*.md` files (security-analysis prose the scanner text-matches without distinguishing from real code). Scanning only the plugin subdirectory avoids that noise entirely.
  - Update later with `hermes plugins update claude-cli-provider`.
- Not pursued: a `pyproject.toml` + `hermes_agent.plugins` pip entry point — now low priority, since `hermes plugins install` already solves the real problem it would have addressed.

## Fase 6 (optional, on demand): dual HTTP mode

Only relevant if a real need appears to reuse this plugin's logic from tools outside Hermes (Open WebUI, Cursor, etc.). See the rejected alternative in [02-is-bridge-necessary.md](./02-is-bridge-necessary.md#alternative-considered-and-rejected). Not built preemptively.

## Permanently out of scope

`model-router` and `zai-proxy` (routing the Claude Code CLI's own model backend to DeepSeek/z.ai) — see [07-scope-and-migration.md](./07-scope-and-migration.md). If ever wanted, it's a separate project, not part of this plugin.
