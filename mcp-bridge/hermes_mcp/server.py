"""Wires cron_tools/kanban_tools functions into an MCP server.

No logic lives here — this module only registers already-tested functions
as tools. `python -m hermes_mcp` (see `__main__.py`) is the actual entry point.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from hermes_mcp import cron_tools, kanban_tools
from hermes_mcp._version import __version__

_TOOLS = (
    cron_tools.cron_list,
    cron_tools.cron_create,
    cron_tools.cron_pause,
    cron_tools.cron_resume,
    cron_tools.cron_remove,
    cron_tools.cron_status,
    kanban_tools.kanban_list,
    kanban_tools.kanban_show,
    kanban_tools.kanban_create,
    kanban_tools.kanban_assign,
    kanban_tools.kanban_comment,
    kanban_tools.kanban_complete,
    kanban_tools.kanban_block,
)


def build_server() -> MCPServer:
    server = MCPServer(
        name="hermes-bridge",
        version=__version__,
        instructions=(
            "Hermes Agent's own native cron and kanban tools, exposed as MCP tools so a "
            "claude-cli-backed Hermes profile can use them (the claude CLI accepts no "
            "per-request tool schemas from its caller, so Hermes' own tools: array never "
            "reaches it — this bridge is configured MCP, which the CLI does support). "
            "Set $HERMES_MCP_PROFILE in this server's environment to target a specific "
            "Hermes profile instead of the default one."
        ),
    )
    for fn in _TOOLS:
        server.tool()(fn)
    return server
