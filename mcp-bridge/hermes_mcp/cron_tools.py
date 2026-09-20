"""MCP tool functions wrapping `hermes cron`.

Each function here becomes one MCP tool once registered in `server.py`. They
stay plain, synchronous functions returning `str` so `tests/test_cron_tools.py`
can call them directly without spinning up an MCP server.
"""

from __future__ import annotations

from hermes_mcp.runner import run_hermes


def cron_list(include_disabled: bool = False) -> str:
    """List Hermes' own recurring scheduled jobs (durable, survive restarts,
    deliver back through Hermes' own channels). Not the built-in session
    CronCreate/CronList/CronDelete tools, which are unrelated to Hermes.
    Set `include_disabled` to also show paused jobs."""
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
    """Create a real, durable recurring job in Hermes' own scheduler — use this
    (not the unrelated built-in session CronCreate tool) whenever the user asks
    to be checked on, reminded, or have something run periodically going
    forward, including across restarts of this chat.

    `schedule` is a cron expression ('0 9-18 * * 1-5') or an interval
    ('every 1h', '30m'). `prompt` is the self-contained instruction the job
    runs each time it fires — required unless a `skill` covers it (the
    underlying `hermes cron create` rejects a call with neither). Set
    `continuity=True` so each run sees its own previous output and only
    reports what changed since then.
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


def cron_edit(
    job_id: str,
    schedule: str = "",
    prompt: str = "",
    name: str = "",
    deliver: str = "",
    repeat: int | None = None,
    continuity: bool = False,
    model: str = "",
    provider: str = "",
    reasoning_effort: str = "",
) -> str:
    """Edit an existing recurring job in place — only the fields passed are
    changed, everything else on the job is left untouched. Prefer this over
    cron_remove + cron_create for any change to a job that's already running:
    editing in place keeps its job_id and execution history, and recreating
    silently drops it. Note: neither this bridge nor the underlying `hermes
    cron` CLI can print a job's current prompt text (cron_list/cron_status/
    cron_runs only expose schedule/name/status, never the prompt) — get the
    current wording from the user, from a durable note, or from a prior
    conversation before overwriting `prompt`.
    """
    args = ["cron", "edit", job_id]
    if schedule:
        args += ["--schedule", schedule]
    if prompt:
        args += ["--prompt", prompt]
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
    """Check whether Hermes' own cron scheduler (not the built-in session
    scheduler) is running."""
    return run_hermes("cron", "status").output
