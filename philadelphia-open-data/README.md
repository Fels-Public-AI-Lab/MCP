# Philadelphia Open Data MCP Server

A [FastMCP](https://github.com/jlowin/fastmcp) server that connects AI assistants to Philadelphia's open data ecosystem — the city's dataset catalog, its public CARTO SQL database, and the Office of Property Assessment's records.

## Tools

The server exposes 12 tools across three modules.

### Catalog (`tools/catalog.py`)

Search and explore the [OpenDataPhilly](https://opendataphilly.org) dataset catalog. The catalog (406 datasets as of 2026) is fetched and cached in memory at startup with a 6-hour TTL.

| Tool | Description |
|------|-------------|
| `catalog_search` | Search datasets by keyword across title, description, and tags. Filter by category or organization. |
| `catalog_get_dataset` | Get full metadata for one dataset by title or URL slug, including resource names and the dataset page URL. |

### CARTO (`tools/carto.py`)

Read-only access to Philadelphia's public CARTO SQL instance (`phl.carto.com`). All queries are validated against a blocklist of SQL write keywords before execution. Maximum 1,000 rows per call.

| Tool | Description |
|------|-------------|
| `carto_get_schema` | Return column names and types for a CARTO table. Uses `SELECT * LIMIT 0` to read the fields metadata without transferring data. |
| `carto_query` | Execute a SELECT query against a CARTO table. Pass a WHERE clause (and optional ORDER BY); the tool wraps it in `SELECT * FROM <table> WHERE ... LIMIT <n>`. |

**Known tables:**

| Table | Contents |
|-------|----------|
| `public_cases_fc` | 311 service requests |
| `incidents_part1_part2` | Police crime incidents (Part I & II) |
| `li_permits` | Licenses & Inspections building permits |
| `li_violations` | L&I code violations |
| `parking_violations` | PPA parking tickets |
| `opa_properties_public` | OPA property records and valuations |

### Property Tax (`tools/property_tax.py`)

Structured tools for Philadelphia Office of Property Assessment data, including assessment equity analysis following IAAO standards. Migrated and extended from the [Philadelphia Property Tax MCP](../philadelphia-property-tax-MCP/).

| Tool | Description |
|------|-------------|
| `philly_search_properties` | Search OPA properties by address, parcel number, or ZIP code. |
| `philly_get_property_details` | Get all 82 available fields for a single parcel. |
| `philly_search_by_characteristics` | Filter properties by physical characteristics: bedrooms, bathrooms, square footage, year built, quality grade, condition, features, and market value. |
| `philly_search_recent_sales` | Find recent property sales, filterable by ZIP code, price range, and time window. |
| `philly_search_assessments` | Query the historical assessments table for taxable and exempt values by year. |
| `philly_search_permits` | Search L&I building permits by address, permit number, type, status, or date range. |
| `philly_analyze_assessment_equity` | Run an IAAO-standard assessment equity analysis: median ASR, COD, PRD, and PRB for a comparison area, with optional subject property comparison. |
| `census_get_demographics` | Retrieve ACS population, age, race/ethnicity, household, and income data from the US Census Bureau API. |

## Installation

```bash
cd philadelphia-open-data
pip install -r requirements.txt
```

**Requirements:** Python 3.10+, packages listed in `requirements.txt` (`fastmcp`, `pydantic`, `httpx`, `python-dotenv`).

## Configuration

Create a `.env` file in the `philadelphia-open-data/` directory:

```
# Optional — Census API requests work without a key but are rate-limited
CENSUS_API_KEY=your_key_here

# Optional overrides
DEFAULT_CENSUS_YEAR=2022
DEFAULT_CENSUS_DATASET=acs/acs5
```

Get a free Census API key at [api.census.gov/data/key_signup.html](https://api.census.gov/data/key_signup.html).

## Connecting to an MCP Client

Add this block to your MCP client's config file (e.g., `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "philadelphia-open-data": {
      "command": "python",
      "args": ["/absolute/path/to/MCP/philadelphia-open-data/server.py"]
    }
  }
}
```

On startup, the server prints the registered tools to stderr and begins listening on stdio.

## Architecture

```
server.py                  — entry point; imports modules to register tools
tools/__init__.py          — creates the shared FastMCP instance
tools/catalog.py           — OpenDataPhilly catalog (in-memory cache)
tools/carto.py             — CARTO SQL API (read-only, validated)
tools/property_tax.py      — OPA assessments, Census demographics
```

All three tool modules share one `mcp` instance defined in `tools/__init__.py`. Importing a module is sufficient to register its tools — `server.py` imports all three before calling `mcp.run()`.

## Data Sources

| Source | URL | Notes |
|--------|-----|-------|
| OpenDataPhilly catalog | `opendataphilly.org/datasets.json` | 406 datasets, refreshed every 6 hours |
| Philadelphia CARTO | `phl.carto.com/api/v2/sql` | Public, no auth required, 60 req/min |
| US Census Bureau | `api.census.gov/data` | Free key recommended |

## Privacy

Owner names (`owner_1`, `owner_2`) are returned as display fields when looking up a property by address or parcel number, consistent with Philadelphia's public records. Searching by owner name is intentionally not supported. AI tools substantially reduce the friction of aggregating public records; this server is designed for property-level transparency, not for enumerating all holdings of an individual or entity. Users who need ownership-based queries can use `carto_query` directly against `opa_properties_public`.

## Example Prompts

- *"Search the Philadelphia open data catalog for air quality datasets"*
- *"What columns are in the parking violations table?"*
- *"Show me 311 service requests in ZIP 19103 from the last week"*
- *"Find properties in 19143 with 3 bedrooms built before 1940"*
- *"Run an assessment equity analysis for residential properties in ZIP 19104"*
- *"Get the assessment history for parcel 883309050"*
- *"What are the demographics for Philadelphia County from the 2022 ACS?"*

---

Part of the [Fels Public AI Lab MCP Servers](../README.md) project.
Fels Institute of Government, University of Pennsylvania — [publicailab@sas.upenn.edu](mailto:publicailab@sas.upenn.edu)
