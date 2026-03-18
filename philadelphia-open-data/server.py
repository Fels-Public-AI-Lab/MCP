"""
Philadelphia Open Data MCP Server

Exposes Philadelphia open data via the Model Context Protocol:
  - Catalog:      search OpenDataPhilly dataset catalog
  - CARTO:        schema inspection and SQL queries against phl.carto.com tables
  - Property Tax: OPA property assessment, sales, permits, and equity analysis
"""

import sys
from tools import mcp

# Import tool modules so their @mcp.tool decorators fire and register tools
import tools.catalog      # noqa: F401
import tools.carto        # noqa: F401
import tools.property_tax # noqa: F401

if __name__ == "__main__":
    print("=" * 60, file=sys.stderr)
    print("Philadelphia Open Data MCP Server", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("[OK] catalog tools:      catalog_search, catalog_get_dataset", file=sys.stderr)
    print("[OK] carto tools:        carto_get_schema, carto_query", file=sys.stderr)
    print("[OK] property tax tools: philly_search_assessments,", file=sys.stderr)
    print("                         philly_search_properties,", file=sys.stderr)
    print("                         philly_get_property_details,", file=sys.stderr)
    print("                         philly_search_by_characteristics,", file=sys.stderr)
    print("                         philly_search_recent_sales,", file=sys.stderr)
    print("                         philly_search_permits,", file=sys.stderr)
    print("                         philly_analyze_assessment_equity,", file=sys.stderr)
    print("                         census_get_demographics", file=sys.stderr)
    print("=" * 60, file=sys.stderr)
    print("Starting MCP server...", file=sys.stderr)

    mcp.run(transport="stdio")
