"""MCP tool functions wrapping `hermes cron`.

Each function here becomes one MCP tool once registered in `server.py`. They
stay plain, synchronous functions returning `str` so `tests/test_cron_tools.py`
can call them directly without spinning up an MCP server.
"""

from __future__ import annotations

from hermes_mcp.runner import run_hermes


def cron_list(include_disabled: bool = False) -> str:
    """List scheduled jobs. Set `include_disabled` to also show paused jobs."""
    args = ["cron", "list"]
    if include_disabled:
        args.append("--all")
    return run_hermes(*args).output


def cron_create(
    schedule: str,
    prompt: str = "",
    name: str = "",
    deliver: str = "",
    repeat: int | None = None,
    continuity: bool = False,
    model: str = "",
    provider: str = "",
    reasoning_effort: str = "",
    paused: bool = False,
) -> str:
    """Create a recurring scheduled job.

    `schedule` is a cron expression ('0 9-18 * * 1-5') or an interval
    ('every 1h', '30m'). `prompt` is the self-contained instruction the job
    runs each time it fires. Set `continuity=True` so each run sees its own
    previous output and only reports what changed since then.
    """
    args = ["cron", "create", schedule]
    if prompt:
        args.append(prompt)
    if name:
        args += ["--name", name]
    if deliver:
        args += ["--deliver", deliver]
    if repeat is not None:
        args += ["--repeat", str(repeat)]
    if continuity:
        args.append("--continuity")
    if model:
        args += ["--model", model]
    if provider:
        args += ["--provider", provider]
    if reasoning_effort:
        args += ["--reasoning-effort", reasoning_effort]
    if paused:
        args.append("--paused")
    return run_hermes(*args).output


def cron_pause(job_id: str) -> str:
    """Pause a scheduled job so it stops firing without deleting it."""
    return run_hermes("cron", "pause", job_id).output


def cron_resume(job_id: str) -> str:
    """Resume a previously paused scheduled job."""
    return run_hermes("cron", "resume", job_id).output


def cron_remove(job_id: str) -> str:
    """Permanently delete a scheduled job."""
    return run_hermes("cron", "remove", job_id).output


def cron_status() -> str:
    """Check whether the cron scheduler is running."""
    return run_hermes("cron", "status").output
