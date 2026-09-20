# Tests

81 tests, all passing (`pytest -q` → `81 passed`). None invoke the real `claude` CLI — subprocesses are simulated with a fake binary in `test_process.py`, and `test_client.py`/`test_config.py`/`test_session.py` use `monkeypatch`. This keeps the suite fast (~0.4s) with no real subscription usage cost.

| File | Covers |
|---|---|
| `test_protocol.py` | message flattening, model alias normalization, `stop_reason` mapping (23 tests) |
| `test_process.py` | argv construction (`build_args`), subprocess spawn/parse (`run_once`), the subprocess environment allowlist (`build_subprocess_env`) — including the real CLI error path and a timeout (20 tests) |
| `test_config.py` | environment variable resolution and defaults (9 tests) |
| `test_client.py` | `ClaudeCLIClient` orchestration (model normalization, permission wiring, response shape, session-continuity fallback behavior) with `run_once` mocked (22 tests) |
| `test_session.py` | `compute_delta()` pure logic — when a turn can safely resume the previous one (6 tests) |
| `test_plugin_init.py` | `plugin/claude_cli/__init__.py` doesn't break when imported outside a real Hermes process (1 test) |

Run everything:
```
cd /mnt/dev/projects-rk/hermes-claude-cli
.venv/bin/python -m pytest -q
```

A real, manual smoke test (not automated, to avoid spending subscription usage on every suite run) is documented in `../docs/08-roadmap.md`.
