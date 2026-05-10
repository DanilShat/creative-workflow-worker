"""MCP server for Claude Desktop on the designer laptop.

Exposes typed, allowlisted tools that talk to the operator API. Designed for
Gate B0 (read-only context + review notes) with room to grow into B1-B3
(browser jobs, Photoshop, After Effects).
"""

from creative_workflow.worker.mcp.server import build_server, run

__all__ = ["build_server", "run"]
