"""CONSENTLEDGER MCP server — exposes scan() as an MCP tool for Cognis.Studio."""
from __future__ import annotations
from consentledger.core import scan, to_json

def serve() -> int:
    """Start an MCP stdio server. Requires the optional 'mcp' extra:
        pip install "cognis-consentledger[mcp]"
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except Exception:
        print("Install the MCP extra: pip install 'cognis-consentledger[mcp]'")
        return 1
    app = FastMCP("consentledger")

    @app.tool()
    def consentledger_scan(target: str) -> str:
        """Maintain a tamper-evident, hash-chained audit log of patient-data access and consent events.. Returns JSON findings."""
        return to_json(scan(target))

    app.run()
    return 0
