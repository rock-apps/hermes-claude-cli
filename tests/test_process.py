from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest

from plugin.claude_cli.process import (
    ClaudeCLIProcessError,
    CLIResult,
    PermissionConfig,
    build_args,
    build_subprocess_env,
    run_once,
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
