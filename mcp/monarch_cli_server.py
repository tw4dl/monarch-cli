"""Entry point for running the Monarch CLI MCP server.

Run:
  uv run --with "mcp>=1.27.1,<2" mcp/monarch_cli_server.py
"""

from __future__ import annotations

import os

from monarch_cli.mcp_server import build_mcp_server


def main() -> None:
    transport = os.environ.get("MONARCH_MCP_TRANSPORT", "stdio")
    build_mcp_server().run(transport=transport)


if __name__ == "__main__":
    main()
