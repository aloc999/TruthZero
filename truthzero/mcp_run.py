"""Entry point for MCP stdio server: python -m truthzero.mcp_run"""
from truthzero.mcp.server import serve

if __name__ == "__main__":
    serve()
