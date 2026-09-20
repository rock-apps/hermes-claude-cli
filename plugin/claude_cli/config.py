"""Environment-variable configuration for the claude-cli provider plugin.

Full configuration surface is documented in ../../docs/07-configuration.md. Unlike the
original claude-bridge, there is no hardcoded list of personal directories — see
../../docs/01-analysis-claude-bridge.md for why that was a problem worth not repeating.

``CLAUDE_CLI_PERMISSION_MODE`` defaults to "auto": Claude Code's own smart
auto-approval heuristic (the same mode this project's own development sessions run
under), combined unconditionally with ``--permission-prompts none`` in process.py so
that anything the heuristic would otherwise stop to ask about is denied instead of
hanging forever with no human to answer. This resolves the security default that was
left open in ../../docs/08-security.md; override via ``CLAUDE_CLI_PERMISSION_MODE``
if a different mode is needed.

``CLAUDE_CLI_RESTRICTED`` defaults to true: this plugin's job is "answer a chat
message", not "act as an agent with Bash/PowerShell/REPL/WebFetch access" — an
unattended provider silently running shell commands as a side effect of an ordinary
Hermes chat turn is a real risk with no upside for that use case. Verified this
doesn't break normal chat behaviour (plain Q&A works identically restricted or not).
Set to false explicitly for a deployment that actually wants claude-cli to act as a
full agent with system access.

``CLAUDE_CLI_SESSION_CONTINUITY`` defaults to true: resume a prior `claude` session
via `--resume` instead of re-flattening the whole conversation on every turn, when
client.py's tracking shows it's safe to (see session.py and docs/10-roadmap.md, Fase
4). Every failure mode falls back to a normal, full-history call automatically —
verified empirically, including the case of a `--resume` target the CLI no longer
recognises. Kept configurable in case a deployment wants to rule the behavior out
entirely rather than rely on the fallback.

``CLAUDE_CLI_MCP_CONFIG`` / ``CLAUDE_CLI_ALLOWED_TOOLS`` (both unset by default, so
restricted mode's own defaults are unchanged unless opted into): confirmed
empirically that ``--restricted`` ignores ambient user/project/local settings —
an MCP server registered via ``claude mcp add --scope user`` is invisible to a
restricted invocation, and any ``permissions.allow`` entry meant to pre-approve a
tool call is ignored too, so it gets silently denied under
``--permission-prompts none`` with no error surfaced back through Hermes. See
``mcp-bridge/README.md`` for a concrete worked example (Hermes' own cron/kanban
CLI, exposed as MCP tools). ``CLAUDE_CLI_MCP_CONFIG`` is passed straight through
to ``--mcp-config`` (a JSON string or a file path, whatever the CLI itself
accepts). ``CLAUDE_CLI_ALLOWED_TOOLS`` is a comma-separated list of tool names,
turned into a ``--settings '{"permissions": {"allow": [...]}}'`` JSON blob —
both flags are the documented exception that still applies even under
``--restricted``.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Mapping
from dataclasses import dataclass, field

_LEGACY_BIN_CANDIDATES = (
    os.path.expanduser("~/.local/bin/claude"),
    "/usr/local/bin/claude",
)
_DEFAULT_MODEL = "sonnet"
_DEFAULT_PERMISSION_MODE = "auto"
_DEFAULT_TIMEOUT_SECONDS = 300.0


@dataclass(frozen=True)
class ClaudeCLIConfig:
    """Resolved configuration for one `claude` CLI invocation."""

    binary: str
    default_model: str = _DEFAULT_MODEL
    allowed_dirs: tuple[str, ...] = field(default_factory=tuple)
    permission_mode: str = _DEFAULT_PERMISSION_MODE
    restricted: bool = True
    max_budget_usd: float | None = None
    timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS
    session_continuity: bool = True
    mcp_config: str | None = None
    allowed_tools: tuple[str, ...] = field(default_factory=tuple)


class ClaudeBinaryNotFoundError(RuntimeError):
    """Raised when no usable `claude` binary can be located."""


def find_claude_binary(env: Mapping[str, str]) -> str:
    """Locate the `claude` CLI binary.

    Resolution order: ``CLAUDE_CLI_BIN`` env var, then ``CLAUDE_BIN`` (legacy name
    from the original claude-bridge, kept for migration convenience), then a couple
    of well-known install locations, then whatever `claude` resolves to on PATH.
    Raises ClaudeBinaryNotFoundError if none of those exist.
    """
    explicit = env.get("CLAUDE_CLI_BIN") or env.get("CLAUDE_BIN")
    if explicit:
        return explicit
    for candidate in _LEGACY_BIN_CANDIDATES:
        if os.path.isfile(candidate):
            return candidate
    found = shutil.which("claude")
    if found:
        return found
    raise ClaudeBinaryNotFoundError(
        "Could not locate the `claude` binary. Set CLAUDE_CLI_BIN=/path/to/claude "
        "or install Claude Code: https://claude.ai/code"
    )


def _parse_allowed_dirs(raw: str) -> tuple[str, ...]:
    home = os.path.expanduser("~")
    dirs: list[str] = []
    for part in raw.split(":"):
        candidate = part.strip()
        if not candidate:
            continue
        if candidate.startswith("~"):
            candidate = home + candidate[1:]
        if os.path.isdir(candidate):
            dirs.append(candidate)
    return tuple(dirs)


def _parse_allowed_tools(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(",") if part.strip())


def _parse_bool(raw: str, *, default: bool) -> bool:
    normalized = raw.strip().lower()
    if not normalized:
        return default
    return normalized in ("1", "true", "yes", "on")


def load_config(env: Mapping[str, str] | None = None) -> ClaudeCLIConfig:
    """Build a ClaudeCLIConfig by reading environment variables.

    Pass an explicit `env` mapping (e.g. in tests) to avoid depending on the real
    process environment; defaults to `os.environ`.
    """
    resolved_env = env if env is not None else os.environ
    max_budget_raw = resolved_env.get("CLAUDE_CLI_MAX_BUDGET_USD", "").strip()
    return ClaudeCLIConfig(
        binary=find_claude_binary(resolved_env),
        default_model=resolved_env.get("CLAUDE_CLI_DEFAULT_MODEL", "").strip()
        or _DEFAULT_MODEL,
        allowed_dirs=_parse_allowed_dirs(resolved_env.get("CLAUDE_CLI_ALLOWED_DIRS", "")),
        permission_mode=resolved_env.get("CLAUDE_CLI_PERMISSION_MODE", "").strip()
        or _DEFAULT_PERMISSION_MODE,
        restricted=_parse_bool(resolved_env.get("CLAUDE_CLI_RESTRICTED", ""), default=True),
        max_budget_usd=float(max_budget_raw) if max_budget_raw else None,
        timeout_seconds=float(
            resolved_env.get("CLAUDE_CLI_TIMEOUT_SECONDS", "") or _DEFAULT_TIMEOUT_SECONDS
        ),
        session_continuity=_parse_bool(
            resolved_env.get("CLAUDE_CLI_SESSION_CONTINUITY", ""), default=True
        ),
        mcp_config=resolved_env.get("CLAUDE_CLI_MCP_CONFIG", "").strip() or None,
        allowed_tools=_parse_allowed_tools(resolved_env.get("CLAUDE_CLI_ALLOWED_TOOLS", "")),
    )
