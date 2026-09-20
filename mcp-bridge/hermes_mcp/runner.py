"""Subprocess wrapper around the `hermes` CLI.

This is the only module that touches `subprocess`. Every MCP tool in
`server.py` goes through `run_hermes()` instead of shelling out itself, so
the profile-targeting and error-handling rules live in exactly one place.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass

# A bare "hermes" only resolves if PATH includes it. A daemonized parent process
# (e.g. hermes-webui launched without the user's shell PATH — confirmed on a real
# deployment to be missing ~/.local/bin entirely, see docs/05-configuration.md) can
# spawn this bridge with a PATH that never included it, even though the binary is
# installed. Checked before falling back to PATH resolution, same pattern as
# plugin/claude_cli/config.py's find_claude_binary for the `claude` binary.
_LEGACY_BIN_CANDIDATES = (
    os.path.expanduser("~/.local/bin/hermes"),
    "/usr/local/bin/hermes",
)


def build_command(*args: str) -> list[str]:
    """The `hermes` argv for `args`, targeting `$HERMES_MCP_PROFILE` if set.

    `$HERMES_MCP_PROFILE` is this bridge's own env var (set at
    `claude mcp add -e HERMES_MCP_PROFILE=<name>` time) — it is not read by
    the `hermes` CLI itself, which only understands `-p <profile>`.
    """
    binary = os.environ.get("HERMES_MCP_BIN")
    if not binary:
        binary = next((c for c in _LEGACY_BIN_CANDIDATES if os.path.isfile(c)), "hermes")
    profile = os.environ.get("HERMES_MCP_PROFILE") or ""
    profile_args = ["-p", profile] if profile else []
    return [binary, *profile_args, *args]


@dataclass(frozen=True)
class HermesResult:
    stdout: str
    stderr: str
    returncode: int | None  # None when the process never actually ran (missing binary, timeout)

    @property
    def ok(self) -> bool:
        return self.returncode == 0

    @property
    def output(self) -> str:
        """The text to hand back to the model: stdout on success, stderr (or both) on failure."""
        if self.ok:
            return self.stdout
        if self.stdout and self.stderr:
            return f"{self.stdout}\n{self.stderr}"
        return self.stderr or self.stdout


_DEFAULT_TIMEOUT_SECONDS = 30.0


def run_hermes(*args: str, timeout: float = _DEFAULT_TIMEOUT_SECONDS) -> HermesResult:
    """Run `hermes *args`, never raising — failures come back as a non-ok `HermesResult`."""
    command = build_command(*args)
    try:
        completed = subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, shell=False, check=False,
        )
    except FileNotFoundError:
        return HermesResult(
            stdout="", stderr=f"'{command[0]}' was not found on PATH — is the hermes CLI installed?",
            returncode=None,
        )
    except subprocess.TimeoutExpired:
        return HermesResult(stdout="", stderr=f"hermes command timed out after {timeout}s: {' '.join(command)}", returncode=None)
    return HermesResult(stdout=completed.stdout, stderr=completed.stderr, returncode=completed.returncode)
