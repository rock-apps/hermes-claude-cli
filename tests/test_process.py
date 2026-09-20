from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from plugin.claude_cli.process import (
    ClaudeCLIProcessError,
    CLIResult,
    PermissionConfig,
    StreamChunk,
    build_args,
    build_subprocess_env,
    run_once,
    run_streaming,
)


def make_fake_claude(tmp_path: Path, *, stdout: str, exit_code: int = 0, sleep_seconds: float = 0.0) -> str:
    script_path = tmp_path / "fake-claude"
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        f"time.sleep({sleep_seconds})\n"
        f"sys.stdout.write({stdout!r})\n"
        f"sys.exit({exit_code})\n"
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    return str(script_path)


def make_fake_claude_streaming(
    tmp_path: Path,
    *,
    lines: list[str],
    exit_code: int = 0,
    delay_before_each: float = 0.0,
) -> str:
    """A fake `claude` binary that prints one line per stdout write, with an
    optional delay before each — used to exercise run_streaming's incremental
    reads and (with a large enough delay) its timeout path."""
    script_path = tmp_path / "fake-claude-streaming"
    lines_literal = repr(lines)
    script_path.write_text(
        "#!/usr/bin/env python3\n"
        "import sys, time\n"
        f"for line in {lines_literal}:\n"
        f"    time.sleep({delay_before_each})\n"
        "    sys.stdout.write(line + chr(10))\n"
        "    sys.stdout.flush()\n"
        f"sys.exit({exit_code})\n"
    )
    script_path.chmod(script_path.stat().st_mode | stat.S_IEXEC)
    return str(script_path)


SUCCESS_PAYLOAD = {
    "duration_api_ms": 2480,
    "stop_reason": "end_turn",
    "session_id": "a918f013-699b-47e0-8a9e-e53e84bb779a",
    "total_cost_usd": 0.06845069999999999,
    "usage": {
        "input_tokens": 10,
        "output_tokens": 65,
        "cache_creation_input_tokens": 32902,
        "cache_read_input_tokens": 13607,
    },
    "is_error": False,
    "subtype": "success",
    "api_error_status": None,
    "result": "4",
    "type": "result",
}

ERROR_PAYLOAD = {
    "duration_api_ms": 0,
    "stop_reason": "stop_sequence",
    "session_id": "e33f2008-6c91-434a-a075-ced6a4f88755",
    "total_cost_usd": 0,
    "usage": {
        "input_tokens": 0,
        "output_tokens": 0,
    },
    "is_error": True,
    "subtype": "success",
    "api_error_status": 404,
    "result": (
        "There's an issue with the selected model (modelo-que-nao-existe). "
        "It may not exist or you may not have access to it. "
        "Run --model to pick a different model."
    ),
    "type": "result",
}


class TestBuildArgs:
    def test_minimal_call_produces_expected_flags_in_order(self) -> None:
        # Arrange
        permissions = PermissionConfig()

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert args == [
            "-p",
            "--print",
            "--model",
            "sonnet",
            "--output-format",
            "json",
            "--permission-prompts",
            "none",
            "--",
            "hello",
        ]

    def test_non_empty_system_prompt_is_inserted_before_permission_flags(self) -> None:
        # Arrange
        permissions = PermissionConfig()

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="be concise",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert args == [
            "-p",
            "--print",
            "--model",
            "sonnet",
            "--output-format",
            "json",
            "--append-system-prompt",
            "be concise",
            "--permission-prompts",
            "none",
            "--",
            "hello",
        ]

    def test_bypass_permissions_ignores_other_permission_fields(self) -> None:
        # Arrange
        permissions = PermissionConfig(
            bypass=True,
            mode="auto",
            prompts_none=True,
            restricted=True,
            allowed_dirs=("/a",),
        )

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--dangerously-skip-permissions" in args
        assert "--permission-mode" not in args
        assert "--permission-prompts" not in args
        assert "--restricted" not in args
        assert "--add-dir" not in args

    def test_permission_mode_is_included_when_bypass_is_false(self) -> None:
        # Arrange
        permissions = PermissionConfig(mode="auto")

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--permission-mode" in args
        assert args[args.index("--permission-mode") + 1] == "auto"

    def test_restricted_flag_is_included_when_set(self) -> None:
        # Arrange
        permissions = PermissionConfig(restricted=True)

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--restricted" in args

    def test_allowed_dirs_produce_one_add_dir_pair_per_directory_in_order(self) -> None:
        # Arrange
        permissions = PermissionConfig(allowed_dirs=("/a", "/b"))

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert args.count("--add-dir") == 2
        first_index = args.index("--add-dir")
        assert args[first_index : first_index + 4] == [
            "--add-dir",
            "/a",
            "--add-dir",
            "/b",
        ]

    def test_mcp_config_is_passed_through_when_set(self) -> None:
        # Arrange
        permissions = PermissionConfig(restricted=True, mcp_config='{"mcpServers":{}}')

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--mcp-config" in args
        assert args[args.index("--mcp-config") + 1] == '{"mcpServers":{}}'

    def test_mcp_config_is_omitted_when_not_set(self) -> None:
        # Arrange
        permissions = PermissionConfig(restricted=True)

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--mcp-config" not in args

    def test_extra_settings_is_passed_through_when_set(self) -> None:
        # Arrange
        permissions = PermissionConfig(restricted=True, extra_settings='{"permissions":{"allow":["x"]}}')

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--settings" in args
        assert args[args.index("--settings") + 1] == '{"permissions":{"allow":["x"]}}'

    def test_extra_settings_is_omitted_when_not_set(self) -> None:
        # Arrange
        permissions = PermissionConfig(restricted=True)

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--settings" not in args

    def test_mcp_config_and_extra_settings_still_apply_under_bypass_permissions(self) -> None:
        # Arrange: --dangerously-skip-permissions short-circuits the other permission
        # flags (mode/prompts-none/restricted/allowed_dirs), but MCP visibility and
        # settings are orthogonal to that branch and must still be threaded through.
        permissions = PermissionConfig(
            bypass=True, mcp_config='{"mcpServers":{}}', extra_settings='{"permissions":{}}',
        )

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert "--mcp-config" in args
        assert "--settings" in args

    def test_max_budget_usd_appends_flag_with_str_value(self) -> None:
        # Arrange
        permissions = PermissionConfig()

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
            max_budget_usd=1.5,
        )

        # Assert
        assert "--max-budget-usd" in args
        assert args[args.index("--max-budget-usd") + 1] == "1.5"

    def test_prompt_is_always_the_last_argument(self) -> None:
        # Arrange
        permissions = PermissionConfig(
            mode="auto",
            restricted=True,
            allowed_dirs=("/a", "/b"),
        )

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="be concise",
            prompt="hello world",
            permissions=permissions,
            max_budget_usd=2.0,
        )

        # Assert
        assert args[-1] == "hello world"

    def test_prompt_is_preceded_by_a_double_dash_separator(self) -> None:
        # Arrange: `--add-dir` is variadic, so without a "--" separator a prompt
        # that doesn't start with "-" is silently swallowed as one more directory
        # instead of reaching `claude` as the prompt — verified empirically against
        # a real `claude` invocation (it fails with "Input must be provided either
        # through stdin or as a prompt argument" when this regresses).
        permissions = PermissionConfig(allowed_dirs=("/a", "/b"))

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert args[-2:] == ["--", "hello"]

    def test_double_dash_separator_present_even_without_allowed_dirs(self) -> None:
        # Arrange: unconditional, not just when allowed_dirs is non-empty — a future
        # variadic flag before the prompt must not reintroduce the same bug.
        permissions = PermissionConfig()

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
        )

        # Assert
        assert args[-2:] == ["--", "hello"]

    def test_stream_true_requests_stream_json_with_partial_messages_and_verbose(
        self,
    ) -> None:
        # Arrange: verified empirically — `--print --output-format stream-json`
        # without `--verbose` is refused ("requires --verbose").
        permissions = PermissionConfig()

        # Act
        args = build_args(
            model="sonnet",
            system_prompt="",
            prompt="hello",
            permissions=permissions,
            stream=True,
        )

        # Assert
        assert "--output-format" in args
        assert args[args.index("--output-format") + 1] == "stream-json"
        assert "--include-partial-messages" in args
        assert "--verbose" in args

    def test_stream_false_still_requests_plain_json(self) -> None:
        # Arrange
        permissions = PermissionConfig()

        # Act
        args = build_args(
            model="sonnet", system_prompt="", prompt="hello", permissions=permissions
        )

        # Assert
        assert args[args.index("--output-format") + 1] == "json"
        assert "--include-partial-messages" not in args
        assert "--verbose" not in args


class TestRunOnce:
    def test_success_case_returns_parsed_cli_result(self, tmp_path: Path) -> None:
        # Arrange
        binary = make_fake_claude(tmp_path, stdout=json.dumps(SUCCESS_PAYLOAD), exit_code=0)

        # Act
        result = run_once(binary, [], timeout=5.0)

        # Assert
        assert result == CLIResult(
            text="4",
            stop_reason="end_turn",
            session_id="a918f013-699b-47e0-8a9e-e53e84bb779a",
            cost_usd=0.06845069999999999,
            input_tokens=10,
            output_tokens=65,
            is_error=False,
            error_message=None,
        )

    def test_cli_reported_error_does_not_raise_and_is_captured_in_result(self, tmp_path: Path) -> None:
        # Arrange
        binary = make_fake_claude(tmp_path, stdout=json.dumps(ERROR_PAYLOAD), exit_code=1)

        # Act
        result = run_once(binary, [], timeout=5.0)

        # Assert
        assert result.is_error is True
        assert result.error_message == ERROR_PAYLOAD["result"]

    def test_unparseable_stdout_raises_process_error(self, tmp_path: Path) -> None:
        # Arrange
        binary = make_fake_claude(tmp_path, stdout="not json at all", exit_code=1)

        # Act / Assert
        with pytest.raises(ClaudeCLIProcessError):
            run_once(binary, [], timeout=5.0)

    def test_missing_binary_raises_process_error(self, tmp_path: Path) -> None:
        # Arrange
        binary = str(tmp_path / "does-not-exist")

        # Act / Assert
        with pytest.raises(ClaudeCLIProcessError):
            run_once(binary, [], timeout=5.0)

    def test_timeout_raises_process_error(self, tmp_path: Path) -> None:
        # Arrange
        binary = make_fake_claude(
            tmp_path,
            stdout=json.dumps(SUCCESS_PAYLOAD),
            exit_code=0,
            sleep_seconds=5.0,
        )

        # Act / Assert
        with pytest.raises(ClaudeCLIProcessError):
            run_once(binary, [], timeout=0.2)

    def test_missing_usage_and_optional_fields_fall_back_to_defaults(self, tmp_path: Path) -> None:
        # Arrange
        minimal_payload = {"result": "hi", "is_error": False}
        binary = make_fake_claude(tmp_path, stdout=json.dumps(minimal_payload), exit_code=0)

        # Act
        result = run_once(binary, [], timeout=5.0)

        # Assert
        assert result == CLIResult(
            text="hi",
            stop_reason=None,
            session_id="",
            cost_usd=0.0,
            input_tokens=0,
            output_tokens=0,
            is_error=False,
            error_message=None,
        )


def _stream_event(delta_type: str, **delta_fields: str) -> str:
    return json.dumps(
        {
            "type": "stream_event",
            "event": {"type": "content_block_delta", "delta": {"type": delta_type, **delta_fields}},
        }
    )


class TestRunStreaming:
    def test_yields_text_deltas_then_final_result(self, tmp_path: Path) -> None:
        # Arrange: shape verified against a real `claude` stream-json invocation.
        lines = [
            _stream_event("text_delta", text="Hel"),
            _stream_event("text_delta", text="lo"),
            json.dumps(SUCCESS_PAYLOAD),
        ]
        binary = make_fake_claude_streaming(tmp_path, lines=lines)

        # Act
        chunks = list(run_streaming(binary, [], timeout=5.0))

        # Assert
        assert chunks[0] == StreamChunk(text_delta="Hel")
        assert chunks[1] == StreamChunk(text_delta="lo")
        assert chunks[2].is_final is True
        assert chunks[2].result.text == "4"

    def test_yields_reasoning_deltas_for_thinking_delta(self, tmp_path: Path) -> None:
        # Arrange
        lines = [
            _stream_event("thinking_delta", thinking="carrying the 1..."),
            json.dumps(SUCCESS_PAYLOAD),
        ]
        binary = make_fake_claude_streaming(tmp_path, lines=lines)

        # Act
        chunks = list(run_streaming(binary, [], timeout=5.0))

        # Assert
        assert chunks[0] == StreamChunk(reasoning_delta="carrying the 1...")

    def test_ignores_unrelated_event_types(self, tmp_path: Path) -> None:
        # Arrange: system/rate_limit_event/assistant/non-delta stream_events are
        # all real event types `claude` emits that carry no incremental text.
        lines = [
            json.dumps({"type": "system", "subtype": "hook_started"}),
            json.dumps({"type": "rate_limit_event", "rate_limit_info": {}}),
            json.dumps({"type": "assistant", "message": {}}),
            json.dumps({"type": "stream_event", "event": {"type": "message_start"}}),
            json.dumps(SUCCESS_PAYLOAD),
        ]
        binary = make_fake_claude_streaming(tmp_path, lines=lines)

        # Act
        chunks = list(run_streaming(binary, [], timeout=5.0))

        # Assert
        assert len(chunks) == 1
        assert chunks[0].is_final is True

    def test_cli_reported_error_returns_final_chunk_without_raising(
        self, tmp_path: Path
    ) -> None:
        # Arrange: verified empirically that an unresumable --resume target comes
        # back as a normal terminal event with is_error=True, not an exception.
        binary = make_fake_claude_streaming(tmp_path, lines=[json.dumps(ERROR_PAYLOAD)], exit_code=1)

        # Act
        (chunk,) = list(run_streaming(binary, [], timeout=5.0))

        # Assert
        assert chunk.is_final is True
        assert chunk.result.is_error is True
        assert chunk.result.error_message == ERROR_PAYLOAD["result"]

    def test_ends_without_a_result_event_raises_process_error(self, tmp_path: Path) -> None:
        # Arrange: process exits (crash) before ever emitting a terminal event.
        binary = make_fake_claude_streaming(
            tmp_path, lines=[_stream_event("text_delta", text="partial")], exit_code=1
        )

        # Act / Assert
        with pytest.raises(ClaudeCLIProcessError):
            list(run_streaming(binary, [], timeout=5.0))

    def test_missing_binary_raises_process_error(self, tmp_path: Path) -> None:
        # Act / Assert
        with pytest.raises(ClaudeCLIProcessError):
            list(run_streaming(str(tmp_path / "does-not-exist"), [], timeout=5.0))

    def test_timeout_raises_process_error(self, tmp_path: Path) -> None:
        # Arrange
        binary = make_fake_claude_streaming(
            tmp_path,
            lines=[_stream_event("text_delta", text="slow"), json.dumps(SUCCESS_PAYLOAD)],
            delay_before_each=5.0,
        )

        # Act / Assert
        with pytest.raises(ClaudeCLIProcessError):
            list(run_streaming(binary, [], timeout=0.2))

    def test_malformed_json_line_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        # Arrange
        lines = ["not json at all", json.dumps(SUCCESS_PAYLOAD)]
        binary = make_fake_claude_streaming(tmp_path, lines=lines)

        # Act
        chunks = list(run_streaming(binary, [], timeout=5.0))

        # Assert
        assert len(chunks) == 1
        assert chunks[0].is_final is True


class TestBuildSubprocessEnv:
    def test_forwards_only_allowlisted_names(self) -> None:
        # Arrange
        source = {
            "HOME": "/home/user",
            "PATH": "/usr/bin:/bin",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "TERM": "xterm",
            "SOME_RANDOM_VAR": "should-not-leak",
        }

        # Act
        env = build_subprocess_env(source)

        # Assert
        assert env == {
            "HOME": "/home/user",
            "PATH": "/usr/bin:/bin",
            "LANG": "en_US.UTF-8",
            "LC_ALL": "en_US.UTF-8",
            "TERM": "xterm",
        }

    def test_never_forwards_anthropic_api_key_even_if_present(self) -> None:
        # Arrange: confirmed empirically that ANTHROPIC_API_KEY, if forwarded,
        # silently overrides the claude CLI's OAuth/Max-subscription session —
        # this is the exact failure this allowlist exists to prevent.
        source = {
            "HOME": "/home/user",
            "PATH": "/usr/bin",
            "ANTHROPIC_API_KEY": "sk-ant-should-never-leak",
            "ANTHROPIC_AUTH_TOKEN": "should-never-leak-either",
        }

        # Act
        env = build_subprocess_env(source)

        # Assert
        assert "ANTHROPIC_API_KEY" not in env
        assert "ANTHROPIC_AUTH_TOKEN" not in env

    def test_missing_optional_vars_are_simply_absent(self) -> None:
        # Arrange
        source = {"HOME": "/home/user", "PATH": "/usr/bin"}

        # Act
        env = build_subprocess_env(source)

        # Assert
        assert env == {"HOME": "/home/user", "PATH": "/usr/bin"}

    def test_defaults_to_os_environ_when_no_source_given(self, monkeypatch) -> None:
        # Arrange
        monkeypatch.setenv("HOME", "/home/from-os-environ")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "leaked-if-this-test-fails")

        # Act
        env = build_subprocess_env()

        # Assert
        assert env.get("HOME") == "/home/from-os-environ"
        assert "ANTHROPIC_API_KEY" not in env
