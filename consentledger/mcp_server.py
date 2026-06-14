"""CONSENTLEDGER MCP server — exposes verify/append as MCP tools for Cognis.Studio."""
from __future__ import annotations
import json
from consentledger.core import verify_ledger


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
    def consentledger_verify(ledger_path: str) -> str:
        """Verify the hash-chain integrity of a consentledger .jsonl file.

        Returns a JSON object with ok, count, head_hash, and errors.
        """
        result = verify_ledger(ledger_path)
        return json.dumps(result.to_dict(), sort_keys=True)

    app.run()
    return 0
