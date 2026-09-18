"""Tests for plugin.claude_cli.client.

`run_once` is monkeypatched throughout — these tests exercise ClaudeCLIClient's own
orchestration (model normalization, permission wiring, completion shape), not the
real `claude` subprocess (already covered by tests/test_process.py).
"""

from __future__ import annotations

from types import SimpleNamespace

from plugin.claude_cli.client import ClaudeCLIClient, _effective_timeout
from plugin.claude_cli.config import ClaudeCLIConfig
from plugin.claude_cli.process import CLIResult


def _make_config(**overrides) -> ClaudeCLIConfig:
    defaults = {
        "binary": "/usr/bin/claude",
        "default_model": "sonnet",
        "allowed_dirs": (),
        "permission_mode": "auto",
        "restricted": False,
        "max_budget_usd": None,
        "timeout_seconds": 300.0,
    }
    defaults.update(overrides)
    return ClaudeCLIConfig(**defaults)


def _success_result(**overrides) -> CLIResult:
    defaults = {
        "text": "4",
        "stop_reason": "end_turn",
        "session_id": "abc-123",
        "cost_usd": 0.01,
        "input_tokens": 10,
        "output_tokens": 5,
        "is_error": False,
        "error_message": None,
    }
    defaults.update(overrides)
    return CLIResult(**defaults)


def test_create_chat_completion_builds_openai_shaped_response(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        "plugin.claude_cli.client.run_once", lambda *a, **k: _success_result()
    )
    client = ClaudeCLIClient(config=_make_config())

    # Act
    completion = client.chat.completions.create(
        model="sonnet", messages=[{"role": "user", "content": "what is 2+2?"}]
    )

    # Assert
    assert completion.object == "chat.completion"
    assert completion.model == "sonnet"
    assert completion.choices[0].message.content == "4"
    assert completion.choices[0].message.role == "assistant"
    assert completion.choices[0].finish_reason == "stop"
    assert completion.usage.prompt_tokens == 10
    assert completion.usage.completion_tokens == 5
    assert completion.usage.total_tokens == 15
    assert completion.is_error is False


def test_create_chat_completion_normalizes_model_alias(monkeypatch) -> None:
    # Arrange
    seen_models: list[str] = []

    def fake_run_once(binary, args, **kwargs):
        seen_models.append(args[args.index("--model") + 1])
        return _success_result()

    monkeypatch.setattr("plugin.claude_cli.client.run_once", fake_run_once)
    client = ClaudeCLIClient(config=_make_config())

    # Act
    completion = client.chat.completions.create(
        model="claude-sonnet-4-6", messages=[{"role": "user", "content": "hi"}]
    )

    # Assert
    assert seen_models == ["sonnet"]
    assert completion.model == "sonnet"


def test_create_chat_completion_falls_back_to_config_default_model(monkeypatch) -> None:
    # Arrange
    seen_models: list[str] = []

    def fake_run_once(binary, args, **kwargs):
        seen_models.append(args[args.index("--model") + 1])
        return _success_result()

    monkeypatch.setattr("plugin.claude_cli.client.run_once", fake_run_once)
    client = ClaudeCLIClient(config=_make_config(default_model="opus"))

    # Act
    client.chat.completions.create(model=None, messages=[{"role": "user", "content": "hi"}])

    # Assert
    assert seen_models == ["opus"]


def test_create_chat_completion_maps_error_result_to_stop_finish_reason(monkeypatch) -> None:
    # Arrange
    error_result = _success_result(
        text="model not found",
        stop_reason="stop_sequence",
        is_error=True,
        error_message="model not found",
        cost_usd=0.0,
        input_tokens=0,
        output_tokens=0,
    )
    monkeypatch.setattr(
        "plugin.claude_cli.client.run_once", lambda *a, **k: error_result
    )
    client = ClaudeCLIClient(config=_make_config())

    # Act
    completion = client.chat.completions.create(
        model="sonnet", messages=[{"role": "user", "content": "hi"}]
    )

    # Assert
    assert completion.is_error is True
    assert completion.error_message == "model not found"
    assert completion.choices[0].finish_reason == "stop"
    assert completion.choices[0].message.content == "model not found"


def test_create_chat_completion_non_streaming_returns_completion_directly(
    monkeypatch,
) -> None:
    # Arrange
    monkeypatch.setattr(
        "plugin.claude_cli.client.run_once", lambda *a, **k: _success_result()
    )
    client = ClaudeCLIClient(config=_make_config())

    # Act
    completion = client.chat.completions.create(
        model="sonnet", messages=[{"role": "user", "content": "hi"}], stream=False
    )

    # Assert
    assert completion.object == "chat.completion"


def _install_fake_acp_openai_bridge(monkeypatch) -> list[SimpleNamespace]:
    """Install a fake `agent.acp_openai_bridge` module in sys.modules so
    client.py's lazy `from agent.acp_openai_bridge import completion_to_stream_chunks`
    resolves without a real Hermes checkout on the test path. Records every
    completion it was called with in the returned list."""
    import sys
    import types

    calls: list[SimpleNamespace] = []

    def fake_completion_to_stream_chunks(completion: SimpleNamespace) -> list[SimpleNamespace]:
        calls.append(completion)
        delta = SimpleNamespace(role="assistant", content=completion.choices[0].message.content)
        data_chunk = SimpleNamespace(
            choices=[SimpleNamespace(index=0, delta=delta, finish_reason=completion.choices[0].finish_reason)],
            model=completion.model,
            usage=None,
        )
        usage_chunk = SimpleNamespace(choices=[], model=completion.model, usage=completion.usage)
        return [data_chunk, usage_chunk]

    fake_agent_pkg = types.ModuleType("agent")
    fake_bridge_module = types.ModuleType("agent.acp_openai_bridge")
    fake_bridge_module.completion_to_stream_chunks = fake_completion_to_stream_chunks
    monkeypatch.setitem(sys.modules, "agent", fake_agent_pkg)
    monkeypatch.setitem(sys.modules, "agent.acp_openai_bridge", fake_bridge_module)
    return calls


def test_create_chat_completion_streaming_converts_via_hermes_bridge_helper(
    monkeypatch,
) -> None:
    # Arrange: verified against a real Hermes Agent process that a stream consumer
    # needs `.choices[i].delta`, not `.choices[i].message` — see client.py.
    monkeypatch.setattr(
        "plugin.claude_cli.client.run_once", lambda *a, **k: _success_result()
    )
    calls = _install_fake_acp_openai_bridge(monkeypatch)
    client = ClaudeCLIClient(config=_make_config())

    # Act
    chunks = list(
        client.chat.completions.create(
            model="sonnet", messages=[{"role": "user", "content": "hi"}], stream=True
        )
    )

    # Assert
    assert len(calls) == 1
    assert calls[0].choices[0].message.content == "4"
    assert chunks[0].choices[0].delta.content == "4"
    assert chunks[1].usage is not None


def test_create_chat_completion_ignores_tools_without_error(monkeypatch) -> None:
    # Arrange
    monkeypatch.setattr(
        "plugin.claude_cli.client.run_once", lambda *a, **k: _success_result()
    )
    client = ClaudeCLIClient(config=_make_config())

    # Act
    completion = client.chat.completions.create(
        model="sonnet",
        messages=[{"role": "user", "content": "hi"}],
        tools=[{"type": "function", "function": {"name": "noop"}}],
        tool_choice="auto",
    )

    # Assert
    assert completion.choices[0].message.tool_calls is None


def test_create_chat_completion_forwards_permission_config(monkeypatch) -> None:
    # Arrange
    seen_args: list[list[str]] = []

    def fake_run_once(binary, args, **kwargs):
        seen_args.append(args)
        return _success_result()

    monkeypatch.setattr("plugin.claude_cli.client.run_once", fake_run_once)
    client = ClaudeCLIClient(
        config=_make_config(
            permission_mode="manual", restricted=True, allowed_dirs=("/repo",)
        )
    )

    # Act
    client.chat.completions.create(model="sonnet", messages=[{"role": "user", "content": "hi"}])

    # Assert
    args = seen_args[0]
    assert "--permission-mode" in args and args[args.index("--permission-mode") + 1] == "manual"
    assert "--restricted" in args
    assert "--add-dir" in args and args[args.index("--add-dir") + 1] == "/repo"
    assert "--dangerously-skip-permissions" not in args


def test_effective_timeout_passes_through_a_plain_float() -> None:
    # Arrange / Act / Assert
    assert _effective_timeout(45.0, default=300.0) == 45.0


def test_effective_timeout_falls_back_to_default_when_none() -> None:
    # Arrange / Act / Assert
    assert _effective_timeout(None, default=300.0) == 300.0


def test_effective_timeout_takes_largest_component_of_httpx_style_timeout() -> None:
    # Arrange: mirrors httpx.Timeout's shape (read/write/connect/pool attributes,
    # no single scalar) — this is the exact object shape Hermes passed in the real
    # E2E run that first surfaced this bug (a bare float broke subprocess.run()).
    timeout_like = SimpleNamespace(read=1800.0, write=5.0, connect=5.0, pool=5.0)

    # Act
    result = _effective_timeout(timeout_like, default=300.0)

    # Assert
    assert result == 1800.0


def test_effective_timeout_falls_back_to_default_when_object_has_no_numeric_fields() -> None:
    # Arrange
    empty_timeout_like = SimpleNamespace()

    # Act
    result = _effective_timeout(empty_timeout_like, default=300.0)

    # Assert
    assert result == 300.0


def test_create_chat_completion_normalizes_httpx_style_timeout(monkeypatch) -> None:
    # Arrange
    seen_timeouts: list[float] = []

    def fake_run_once(binary, args, *, timeout):
        seen_timeouts.append(timeout)
        return _success_result()

    monkeypatch.setattr("plugin.claude_cli.client.run_once", fake_run_once)
    client = ClaudeCLIClient(config=_make_config(timeout_seconds=300.0))
    httpx_style_timeout = SimpleNamespace(read=1800.0, write=5.0, connect=5.0, pool=5.0)

    # Act
    client.chat.completions.create(
        model="sonnet",
        messages=[{"role": "user", "content": "hi"}],
        timeout=httpx_style_timeout,
    )

    # Assert
    assert seen_timeouts == [1800.0]


def test_close_does_not_raise() -> None:
    # Arrange
    client = ClaudeCLIClient(config=_make_config())

    # Act / Assert
    client.close()
