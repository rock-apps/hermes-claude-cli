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
            "Hermes profile instead of the default one.\n\n"
            "IMPORTANT — do not confuse these with the unrelated built-in session tools "
            "named CronCreate/CronList/CronDelete: those schedule a wake-up for THIS "
            "Claude session and have nothing to do with Hermes. The tools in THIS server "
            "(cron_create, cron_list, ...) create real, durable jobs in Hermes' own "
            "scheduler, which persist across restarts and actually message the user back "
            "through Hermes' own delivery channels (Slack, Telegram, etc.) — use these, "
            "not the built-in ones, for anything the user describes as a recurring check, "
            "reminder, or scheduled task they want Hermes itself to run."
        ),
    )
    for fn in _TOOLS:
        server.tool()(fn)
    return server
