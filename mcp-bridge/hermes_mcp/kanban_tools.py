"""MCP tool functions wrapping `hermes kanban`.

Each function here becomes one MCP tool once registered in `server.py`. They
stay plain, synchronous functions returning `str` so `tests/test_kanban_tools.py`
can call them directly without spinning up an MCP server.
"""

from __future__ import annotations

from hermes_mcp.runner import run_hermes


def kanban_list(assignee: str = "", status: str = "", mine: bool = False) -> str:
    """List kanban tasks, optionally filtered by assignee, status, or `mine=True`
    (tasks assigned to this bridge's own `$HERMES_MCP_PROFILE`)."""
    args = ["kanban", "list"]
    if assignee:
        args += ["--assignee", assignee]
    if status:
        args += ["--status", status]
    if mine:
        args.append("--mine")
    return run_hermes(*args).output


def kanban_show(task_id: str) -> str:
    """Show a task's title, body, comments, and current status."""
    return run_hermes("kanban", "show", task_id).output


def kanban_create(title: str, assignee: str = "", body: str = "") -> str:
    """Create a new kanban task, optionally assigned to a named Hermes profile.

    A task with no `assignee` sits unassigned until someone claims or is
    assigned to it. This is the cross-profile handoff primitive: assigning a
    task to another profile queues it for that profile's own dispatcher to
    pick up and execute with that profile's own model/tools.
    """
    args = ["kanban", "create", title]
    if assignee:
        args += ["--assignee", assignee]
    if body:
        args += ["--body", body]
    return run_hermes(*args).output


def kanban_assign(task_id: str, profile: str) -> str:
    """Assign (or reassign) a task to a named profile, or 'none' to unassign."""
    return run_hermes("kanban", "assign", task_id, profile).output


def kanban_comment(task_id: str, text: str) -> str:
    """Append a comment to a task."""
    return run_hermes("kanban", "comment", task_id, text).output


def kanban_complete(task_id: str, summary: str = "") -> str:
    """Mark a task done, optionally with a structured handoff summary for
    whatever depends on it."""
    args = ["kanban", "complete", task_id]
    if summary:
        args += ["--summary", summary]
    return run_hermes(*args).output


def kanban_block(task_id: str, reason: str) -> str:
    """Mark a task blocked with a reason, so a human (or a dependency) can
    unblock it later."""
    return run_hermes("kanban", "block", task_id, reason).output
