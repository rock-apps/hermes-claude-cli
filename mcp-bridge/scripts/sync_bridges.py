#!/usr/bin/env python3
"""Regenerate CLAUDE_CLI_MCP_CONFIG / CLAUDE_CLI_ALLOWED_TOOLS for a set of profiles.

Why this exists: the claude-cli plugin has no way to discover which Hermes profile
is currently being served (create_client() receives no profile identity — see
../../docs/07-scope-and-migration.md) so each profile needs its own hardcoded
hermes-bridge-<profile> MCP server entry (HERMES_MCP_PROFILE=<profile>) registered
in CLAUDE_CLI_MCP_CONFIG, plus its 13 tool names in CLAUDE_CLI_ALLOWED_TOOLS. This
script generates and writes both values so that step is one command instead of
manual JSON surgery, for both the shared multiplex .env and each profile's own.

Usage:
    sync_bridges.py --bridge-bin /path/to/hermes-mcp-bridge \\
        --env-file ~/.hermes/.env --profiles erick,rockapps,financeiro,...
    sync_bridges.py --bridge-bin /path/to/hermes-mcp-bridge \\
        --env-file ~/.hermes/profiles/erick/.env --profiles erick

Pass every profile that should be reachable through a given .env file: the shared
`~/.hermes/.env` (read by the multiplexed gateway) needs every profile; each
profile's own `~/.hermes/profiles/<name>/.env` (read by standalone `hermes -z`)
only needs itself. See mcp-bridge/README.md for the full multiplex-vs-standalone
explanation.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hermes_mcp import cron_tools, kanban_tools

_TOOLS = (
    cron_tools.cron_list,
    cron_tools.cron_create,
    cron_tools.cron_edit,
    cron_tools.cron_pause,
    cron_tools.cron_resume,
    cron_tools.cron_remove,
    cron_tools.cron_status,
    cron_tools.cron_run,
    cron_tools.cron_runs,
    cron_tools.cron_doctor,
    cron_tools.cron_incidents,
    kanban_tools.kanban_list,
    kanban_tools.kanban_show,
    kanban_tools.kanban_create,
    kanban_tools.kanban_assign,
    kanban_tools.kanban_comment,
    kanban_tools.kanban_complete,
    kanban_tools.kanban_block,
    kanban_tools.kanban_unblock,
    kanban_tools.kanban_archive,
    kanban_tools.kanban_stats,
    kanban_tools.kanban_runs,
    kanban_tools.kanban_context,
)
TOOL_NAMES = tuple(fn.__name__ for fn in _TOOLS)


def build_mcp_config(profiles: list[str], bridge_bin: str) -> str:
    servers = {
        f"hermes-bridge-{profile}": {
            "command": bridge_bin,
            "env": {"HERMES_MCP_PROFILE": profile},
        }
        for profile in profiles
    }
    return json.dumps({"mcpServers": servers})


def build_allowed_tools(profiles: list[str]) -> str:
    names = [
        f"mcp__hermes-bridge-{profile}__{tool}"
        for profile in profiles
        for tool in TOOL_NAMES
    ]
    return ",".join(names)


def upsert_env_var(content: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.MULTILINE)
    line = f"{key}={value}"
    if pattern.search(content):
        return pattern.sub(line, content, count=1)
    separator = "" if content.endswith("\n") or not content else "\n"
    return f"{content}{separator}{line}\n"


def sync_env_file(path: Path, profiles: list[str], bridge_bin: str) -> None:
    content = path.read_text() if path.exists() else ""
    if path.exists():
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        backup = path.with_name(f"{path.name}.bak-{timestamp}")
        shutil.copy2(path, backup)
    content = upsert_env_var(content, "CLAUDE_CLI_MCP_CONFIG", f"'{build_mcp_config(profiles, bridge_bin)}'")
    content = upsert_env_var(content, "CLAUDE_CLI_ALLOWED_TOOLS", build_allowed_tools(profiles))
    path.write_text(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--profiles", required=True, help="Comma-separated Hermes profile names")
    parser.add_argument("--bridge-bin", required=True, help="Absolute path to the hermes-mcp-bridge executable")
    parser.add_argument("--env-file", action="append", required=True, dest="env_files", help="Repeatable: .env file to update")
    args = parser.parse_args()

    profiles = [p.strip() for p in args.profiles.split(",") if p.strip()]
    if not profiles:
        parser.error("--profiles must list at least one profile")

    for raw_path in args.env_files:
        path = Path(raw_path).expanduser()
        sync_env_file(path, profiles, args.bridge_bin)
        print(f"updated {path} for profiles: {', '.join(profiles)}")


if __name__ == "__main__":
    main()
