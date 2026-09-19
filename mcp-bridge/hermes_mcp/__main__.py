"""Entry point: `python -m hermes_mcp` runs the bridge over stdio.

This is the command `claude mcp add hermes-bridge -- python3 -m hermes_mcp`
(or the installed console script) spawns.
"""

from __future__ import annotations

from hermes_mcp.server import build_server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
