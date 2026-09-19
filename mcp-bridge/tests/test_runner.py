"""Tests for hermes_mcp.runner — the subprocess wrapper around the `hermes` CLI."""

from __future__ import annotations

import subprocess

import pytest

from hermes_mcp.runner import HermesResult, build_command, run_hermes


class TestBuildCommand:
    def test_defaults_to_the_bare_hermes_binary_with_no_profile(self, monkeypatch):
        monkeypatch.delenv("HERMES_MCP_PROFILE", raising=False)
        monkeypatch.delenv("HERMES_MCP_BIN", raising=False)

        command = build_command("cron", "list")

        assert command == ["hermes", "cron", "list"]

    def test_inserts_profile_flag_when_hermes_mcp_profile_is_set(self, monkeypatch):
        monkeypatch.setenv("HERMES_MCP_PROFILE", "rockapps")
        monkeypatch.delenv("HERMES_MCP_BIN", raising=False)

        command = build_command("kanban", "list")

        assert command == ["hermes", "-p", "rockapps", "kanban", "list"]

    def test_uses_hermes_mcp_bin_override_when_set(self, monkeypatch):
        monkeypatch.setenv("HERMES_MCP_BIN", "/opt/hermes/bin/hermes")
        monkeypatch.delenv("HERMES_MCP_PROFILE", raising=False)

        command = build_command("cron", "status")

        assert command == ["/opt/hermes/bin/hermes", "cron", "status"]

    def test_empty_hermes_mcp_profile_is_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("HERMES_MCP_PROFILE", "")
        monkeypatch.delenv("HERMES_MCP_BIN", raising=False)

        command = build_command("cron", "list")

        assert command == ["hermes", "cron", "list"]


class TestRunHermes:
    def test_returns_stdout_and_ok_true_on_success(self, monkeypatch):
        def fake_run(command, **kwargs):
            assert command == ["hermes", "cron", "list"]
            return subprocess.CompletedProcess(command, returncode=0, stdout="job-1\njob-2\n", stderr="")

        monkeypatch.delenv("HERMES_MCP_PROFILE", raising=False)
        monkeypatch.delenv("HERMES_MCP_BIN", raising=False)
        monkeypatch.setattr(subprocess, "run", fake_run)

        result = run_hermes("cron", "list")

        assert isinstance(result, HermesResult)
        assert result.ok is True
        assert result.stdout == "job-1\njob-2\n"
        assert result.returncode == 0

    def test_captures_stderr_and_ok_false_on_nonzero_exit(self, monkeypatch):
        def fake_run(command, **kwargs):
            return subprocess.CompletedProcess(command, returncode=1, stdout="", stderr="job not found\n")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = run_hermes("cron", "pause", "does-not-exist")

        assert result.ok is False
        assert result.returncode == 1
        assert "job not found" in result.stderr

    def test_missing_hermes_binary_returns_a_result_instead_of_raising(self, monkeypatch):
        def fake_run(command, **kwargs):
            raise FileNotFoundError(f"No such file or directory: {command[0]!r}")

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = run_hermes("cron", "list")

        assert result.ok is False
        assert result.returncode is None
        assert "hermes" in result.stderr.lower()

    def test_timeout_returns_a_result_instead_of_raising(self, monkeypatch):
        def fake_run(command, **kwargs):
            raise subprocess.TimeoutExpired(cmd=command, timeout=kwargs.get("timeout"))

        monkeypatch.setattr(subprocess, "run", fake_run)

        result = run_hermes("cron", "list", timeout=5.0)

        assert result.ok is False
        assert result.returncode is None
        assert "timed out" in result.stderr.lower()

    def test_passes_timeout_through_to_subprocess_run(self, monkeypatch):
        captured = {}

        def fake_run(command, **kwargs):
            captured["timeout"] = kwargs.get("timeout")
            return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        run_hermes("cron", "list", timeout=12.5)

        assert captured["timeout"] == 12.5

    def test_never_uses_a_shell(self, monkeypatch):
        captured = {}

        def fake_run(command, **kwargs):
            captured["shell"] = kwargs.get("shell", False)
            return subprocess.CompletedProcess(command, returncode=0, stdout="", stderr="")

        monkeypatch.setattr(subprocess, "run", fake_run)

        run_hermes("kanban", "comment", "t1", "hello; rm -rf /")

        assert captured["shell"] is False


class TestHermesResultOutput:
    def test_output_returns_stdout_when_ok(self):
        result = HermesResult(stdout="all good\n", stderr="", returncode=0)

        assert result.output == "all good\n"

    def test_output_falls_back_to_stderr_when_not_ok_and_stdout_empty(self):
        result = HermesResult(stdout="", stderr="boom\n", returncode=1)

        assert result.output == "boom\n"

    def test_output_combines_stdout_and_stderr_when_both_present_on_failure(self):
        result = HermesResult(stdout="partial output\n", stderr="then it failed\n", returncode=1)

        assert "partial output" in result.output
        assert "then it failed" in result.output


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
