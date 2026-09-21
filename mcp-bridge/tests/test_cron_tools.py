"""Tests for hermes_mcp.cron_tools — MCP tool functions wrapping `hermes cron`."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hermes_mcp import cron_tools
from hermes_mcp.runner import HermesResult


def _ok(stdout: str = "ok\n") -> HermesResult:
    return HermesResult(stdout=stdout, stderr="", returncode=0)


class TestCronList:
    def test_lists_enabled_jobs_by_default(self, monkeypatch):
        fake = MagicMock(return_value=_ok("job-1  0 9 * * 1-5\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_list()

        fake.assert_called_once_with("cron", "list")
        assert "job-1" in result

    def test_include_disabled_adds_the_all_flag(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_list(include_disabled=True)

        fake.assert_called_once_with("cron", "list", "--all")


class TestCronCreate:
    def test_minimal_call_passes_schedule_only(self, monkeypatch):
        fake = MagicMock(return_value=_ok("Created job t_abc\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_create(schedule="every 1h")

        fake.assert_called_once_with("cron", "create", "every 1h")
        assert "t_abc" in result

    def test_prompt_is_appended_as_a_positional_argument(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_create(schedule="0 9 * * 1-5", prompt="check Sharp and TLE")

        fake.assert_called_once_with("cron", "create", "0 9 * * 1-5", "check Sharp and TLE")

    def test_all_optional_flags_are_forwarded_when_provided(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_create(
            schedule="every 1h",
            prompt="check pending items",
            name="check-pendentes",
            deliver="bot-chat:rockapps",
            repeat=5,
            continuity=True,
            model="opus",
            provider="anthropic",
            reasoning_effort="low",
            paused=True,
        )

        fake.assert_called_once_with(
            "cron", "create", "every 1h", "check pending items",
            "--name", "check-pendentes",
            "--deliver", "bot-chat:rockapps",
            "--repeat", "5",
            "--continuity",
            "--model", "opus",
            "--provider", "anthropic",
            "--reasoning-effort", "low",
            "--paused",
        )

    def test_falsy_optional_flags_are_omitted(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_create(schedule="every 1h", continuity=False, paused=False)

        fake.assert_called_once_with("cron", "create", "every 1h")


class TestCronEdit:
    def test_minimal_call_passes_only_job_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok("Updated job t_abc\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_edit(job_id="t_abc")

        fake.assert_called_once_with("cron", "edit", "t_abc")
        assert "Updated" in result

    def test_all_optional_flags_are_forwarded_when_provided(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_edit(
            job_id="t_abc",
            schedule="every 2h",
            prompt="new instructions",
            name="renamed-job",
            deliver="bot-chat:rockapps",
            repeat=3,
            continuity=True,
            model="opus",
            provider="anthropic",
            reasoning_effort="high",
        )

        fake.assert_called_once_with(
            "cron", "edit", "t_abc",
            "--schedule", "every 2h",
            "--prompt", "new instructions",
            "--name", "renamed-job",
            "--deliver", "bot-chat:rockapps",
            "--repeat", "3",
            "--continuity",
            "--model", "opus",
            "--provider", "anthropic",
            "--reasoning-effort", "high",
        )

    def test_falsy_optional_flags_are_omitted(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_edit(job_id="t_abc", continuity=False)

        fake.assert_called_once_with("cron", "edit", "t_abc")


class TestCronLifecycle:
    def test_pause_targets_the_job_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_pause(job_id="t_abc")

        fake.assert_called_once_with("cron", "pause", "t_abc")

    def test_resume_targets_the_job_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_resume(job_id="t_abc")

        fake.assert_called_once_with("cron", "resume", "t_abc")

    def test_remove_targets_the_job_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_remove(job_id="t_abc")

        fake.assert_called_once_with("cron", "remove", "t_abc")

    def test_status_takes_no_arguments(self, monkeypatch):
        fake = MagicMock(return_value=_ok("scheduler running\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_status()

        fake.assert_called_once_with("cron", "status")
        assert "running" in result

    def test_run_targets_the_job_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_run(job_id="t_abc")

        fake.assert_called_once_with("cron", "run", "t_abc")


class TestCronRuns:
    def test_no_arguments_lists_every_job(self, monkeypatch):
        fake = MagicMock(return_value=_ok("run-1 completed\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_runs()

        fake.assert_called_once_with("cron", "runs")
        assert "run-1" in result

    def test_job_id_filters_to_one_job(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_runs(job_id="t_abc")

        fake.assert_called_once_with("cron", "runs", "t_abc")

    def test_limit_is_forwarded_as_a_string(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_runs(limit=10)

        fake.assert_called_once_with("cron", "runs", "--limit", "10")

    def test_job_id_and_limit_together(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_runs(job_id="t_abc", limit=5)

        fake.assert_called_once_with("cron", "runs", "t_abc", "--limit", "5")


class TestCronDoctor:
    def test_takes_no_arguments(self, monkeypatch):
        fake = MagicMock(return_value=_ok("all jobs healthy\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_doctor()

        fake.assert_called_once_with("cron", "doctor")
        assert "healthy" in result


class TestCronIncidents:
    def test_defaults_to_listing(self, monkeypatch):
        fake = MagicMock(return_value=_ok("incident-1 detected\n"))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_incidents()

        fake.assert_called_once_with("cron", "incidents", "list")
        assert "incident-1" in result

    def test_state_filter_is_forwarded(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_incidents(state="detected")

        fake.assert_called_once_with("cron", "incidents", "list", "--state", "detected")

    def test_ack_action_targets_an_incident_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        cron_tools.cron_incidents(action="ack", incident_id="inc_1")

        fake.assert_called_once_with("cron", "incidents", "ack", "inc_1")


class TestErrorSurfacing:
    def test_a_failing_call_still_returns_text_instead_of_raising(self, monkeypatch):
        fake = MagicMock(return_value=HermesResult(stdout="", stderr="job not found\n", returncode=1))
        monkeypatch.setattr(cron_tools, "run_hermes", fake)

        result = cron_tools.cron_pause(job_id="does-not-exist")

        assert "job not found" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
