"""
Baltimore Open Data MCP Server

Exposes read-only tools for Baltimore's ArcGIS Open Data and Enterprise GIS
services so MCP clients can search datasets, inspect schemas, and query feature
layers directly.
"""

import sys

from tools import mcp

# Import tool modules so their @mcp.tool decorators fire and register tools.
import tools.arcgis  # noqa: F401


if __name__ == "__main__":
    print("=" * 60, file=sys.stderr)
    print("Baltimore Open Data MCP Server", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("[OK] arcgis tools: baltimore_catalog_search,", file=sys.stderr)
    print("                    baltimore_get_service,", file=sys.stderr)
    print("                    baltimore_get_layer_schema,", file=sys.stderr)
    print("                    baltimore_query_layer", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Starting MCP server...", file=sys.stderr)

    mcp.run(transport="stdio")
