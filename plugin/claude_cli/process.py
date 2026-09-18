"""Spawn and parse the `claude` CLI subprocess — no HTTP server involved.

Always requests `--output-format json` and always tries to parse stdout as JSON
regardless of exit code, because the CLI reports its own API-level errors inside a
well-formed JSON payload rather than via a non-JSON crash — verified empirically
against a real `claude` CLI invocation, not assumed.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class ClaudeCLIProcessError(RuntimeError):
    """Raised when the `claude` subprocess cannot be launched, times out, or its
    stdout cannot be parsed as JSON at all. NOT raised for an API-level error the CLI
    itself reports inside a well-formed JSON result (see CLIResult.is_error)."""


@dataclass(frozen=True)
class CLIResult:
    """A parsed `claude` CLI JSON result (the `type: "result"` payload)."""

    text: str
    stop_reason: str | None
    session_id: str
    cost_usd: float
    input_tokens: int
    output_tokens: int
    is_error: bool
    error_message: str | None


@dataclass(frozen=True)
class PermissionConfig:
    """Permission-related flags for one `claude` invocation."""

    bypass: bool = False
    mode: str | None = None
    prompts_none: bool = True
    restricted: bool = False
    allowed_dirs: tuple[str, ...] = field(default_factory=tuple)


def build_args(
    *,
    model: str,
    system_prompt: str,
    prompt: str,
    permissions: PermissionConfig,
    max_budget_usd: float | None = None,
) -> list[str]:
    """Build the argv tail for a `claude` invocation (everything after the binary
    path itself — the caller supplies the binary path separately to `run_once`).
    """
    args = ["-p", "--print", "--model", model, "--output-format", "json"]

    if system_prompt:
        args += ["--append-system-prompt", system_prompt]

    if permissions.bypass:
        args.append("--dangerously-skip-permissions")
    else:
        if permissions.mode:
            args += ["--permission-mode", permissions.mode]
        if permissions.prompts_none:
            args += ["--permission-prompts", "none"]
        if permissions.restricted:
            args.append("--restricted")
        for directory in permissions.allowed_dirs:
            args += ["--add-dir", directory]

    if max_budget_usd is not None:
        args += ["--max-budget-usd", str(max_budget_usd)]

    args.append(prompt)
    return args


def run_once(
    binary: str,
    args: list[str],
    *,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: float = 300.0,
) -> CLIResult:
    """Run `[binary, *args]` as a subprocess and parse its stdout into a CLIResult."""
    try:
        completed = subprocess.run(
            [binary, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd,
            env=env,
            check=False,  # non-zero exit is inspected below, not exceptional here
        )
    except FileNotFoundError as exc:
        raise ClaudeCLIProcessError(f"claude binary not found: {binary}") from exc
    except subprocess.TimeoutExpired as exc:
        raise ClaudeCLIProcessError(
            f"claude subprocess timed out after {timeout}s"
        ) from exc

    # Parse stdout first, before looking at the exit code: the CLI reports its own
    # API-level errors (bad model, etc.) inside a well-formed JSON payload with
    # is_error=true, not via a non-JSON crash — a non-zero exit code alone is not
    # evidence of an unparseable response.
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        stderr = completed.stderr.strip() or "no stderr"
        raise ClaudeCLIProcessError(
            f"claude subprocess produced unparseable stdout "
            f"(exit code {completed.returncode}): {stderr}"
        ) from exc

    usage = payload.get("usage") or {}
    is_error = bool(payload.get("is_error", False))
    text = payload.get("result", "")

    result = CLIResult(
        text=text,
        stop_reason=payload.get("stop_reason"),
        session_id=payload.get("session_id", ""),
        cost_usd=payload.get("total_cost_usd", 0.0),
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        is_error=is_error,
        error_message=text if is_error else None,
    )
    logger.debug(
        "claude result: stop_reason=%r cost_usd=%r is_error=%r",
        result.stop_reason,
        result.cost_usd,
        result.is_error,
    )
    return result
