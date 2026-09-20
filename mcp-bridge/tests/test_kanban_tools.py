"""Tests for hermes_mcp.kanban_tools — MCP tool functions wrapping `hermes kanban`."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from hermes_mcp import kanban_tools
from hermes_mcp.runner import HermesResult


def _ok(stdout: str = "ok\n") -> HermesResult:
    return HermesResult(stdout=stdout, stderr="", returncode=0)


class TestKanbanList:
    def test_lists_all_tasks_by_default(self, monkeypatch):
        fake = MagicMock(return_value=_ok("t_1  ready\n"))
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        result = kanban_tools.kanban_list()

        fake.assert_called_once_with("kanban", "list")
        assert "t_1" in result

    def test_assignee_filter_is_forwarded(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_list(assignee="reviewer")

        fake.assert_called_once_with("kanban", "list", "--assignee", "reviewer")

    def test_status_filter_is_forwarded(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_list(status="ready")

        fake.assert_called_once_with("kanban", "list", "--status", "ready")

    def test_mine_flag_is_forwarded(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_list(mine=True)

        fake.assert_called_once_with("kanban", "list", "--mine")


class TestKanbanShow:
    def test_targets_the_task_id(self, monkeypatch):
        fake = MagicMock(return_value=_ok("title: fix bug\n"))
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        result = kanban_tools.kanban_show(task_id="t_abc")

        fake.assert_called_once_with("kanban", "show", "t_abc")
        assert "fix bug" in result


class TestKanbanCreate:
    def test_minimal_call_passes_title_only(self, monkeypatch):
        fake = MagicMock(return_value=_ok("Created task t_new\n"))
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        result = kanban_tools.kanban_create(title="research ICP funding")

        fake.assert_called_once_with("kanban", "create", "research ICP funding")
        assert "t_new" in result

    def test_assignee_and_body_are_forwarded_when_provided(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_create(title="code review", assignee="reviewer", body="focus on the auth module")

        fake.assert_called_once_with(
            "kanban", "create", "code review",
            "--assignee", "reviewer",
            "--body", "focus on the auth module",
        )


class TestKanbanWorkflowActions:
    def test_assign_targets_task_and_profile(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_assign(task_id="t_abc", profile="reviewer")

        fake.assert_called_once_with("kanban", "assign", "t_abc", "reviewer")

    def test_comment_targets_task_and_text(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_comment(task_id="t_abc", text="looks good to me")

        fake.assert_called_once_with("kanban", "comment", "t_abc", "looks good to me")

    def test_complete_without_summary(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_complete(task_id="t_abc")

        fake.assert_called_once_with("kanban", "complete", "t_abc")

    def test_complete_with_summary(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_complete(task_id="t_abc", summary="fixed in commit abc123")

        fake.assert_called_once_with("kanban", "complete", "t_abc", "--summary", "fixed in commit abc123")

    def test_block_targets_task_and_reason(self, monkeypatch):
        fake = MagicMock(return_value=_ok())
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        kanban_tools.kanban_block(task_id="t_abc", reason="waiting on API credentials")

        fake.assert_called_once_with("kanban", "block", "t_abc", "waiting on API credentials")


class TestErrorSurfacing:
    def test_a_failing_call_still_returns_text_instead_of_raising(self, monkeypatch):
        fake = MagicMock(return_value=HermesResult(stdout="", stderr="task not found\n", returncode=1))
        monkeypatch.setattr(kanban_tools, "run_hermes", fake)

        result = kanban_tools.kanban_show(task_id="does-not-exist")

        assert "task not found" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
