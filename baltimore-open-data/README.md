# Baltimore Open Data MCP Server

A read-only [FastMCP](https://github.com/jlowin/fastmcp) server for chatting with
City of Baltimore datasets published through ArcGIS Open Data and ArcGIS
Enterprise REST services.

The server connects to two public ArcGIS service roots:

| Root | Endpoint | Notes |
|------|----------|-------|
| `geodata` | `https://geodata.baltimorecity.gov/egis/rest/services` | Primary public GIS services and folders such as `CityView`, `Housing`, `Planning`, and `DOF`. |
| `open_data` | `https://opendata.baltimorecity.gov/egis/rest/services` | ArcGIS Open Data services where they are anonymously accessible. Some hosted portal items return `Token Required`. |

## Tools

| Tool | Description |
|------|-------------|
| `baltimore_catalog_search` | Search service names, folders, descriptions, keywords, and layer names across Baltimore ArcGIS catalogs. |
| `baltimore_get_service` | Get metadata for one ArcGIS service, including layers, tables, extents, keywords, and query limits. |
| `baltimore_get_layer_schema` | Inspect one layer or table schema, including field names, aliases, data types, geometry type, and object ID field. |
| `baltimore_query_layer` | Query rows from one layer using an ArcGIS SQL `WHERE` clause. Results are capped at 2,000 records per call and are read-only. |

## Installation

```bash
cd baltimore-open-data
pip install -r requirements.txt
```

Requirements: Python 3.10+ and the packages listed in `requirements.txt`.

## Connecting to an MCP Client

Add this block to your MCP client's config file, adjusting the absolute path:

```json
{
  "mcpServers": {
    "baltimore-open-data": {
      "command": "python",
      "args": ["/absolute/path/to/MCP/baltimore-open-data/server.py"]
    }
  }
}
```

On this machine, the server path is:

```text
C:\Users\dylan\OneDrive - PennO365\Fels Public AI Lab\MCP\baltimore-open-data\server.py
```

## Example Prompts

- "Search Baltimore open data for property."
- "Find Baltimore GIS datasets related to property."
- "What layers are in `CityView/Realproperty_OB`?"
- "Show me the schema for `CityView/Realproperty_OB` layer 0."
- "Query 25 rows from `CityView/Realproperty_OB` where `1=1`."
- "Search the geodata root for neighborhoods, then inspect the matching layer."

## Query Notes

Use `baltimore_catalog_search` first to discover `root`, `service_path`,
`service_type`, and layer IDs. Then use `baltimore_get_layer_schema` to inspect
the available fields before calling `baltimore_query_layer`.

For example:

```json
{
  "root": "geodata",
  "service_path": "CityView/Realproperty_OB",
  "service_type": "FeatureServer",
  "layer_id": 0,
  "where": "1=1",
  "out_fields": "*",
  "limit": 25,
  "return_geometry": false
}
```

The query tool rejects common SQL write keywords and only calls ArcGIS REST
`query` endpoints.

## Architecture

```text
server.py          - entry point; imports tools and starts FastMCP over stdio
tools/__init__.py  - shared FastMCP instance
tools/arcgis.py    - Baltimore ArcGIS catalog, schema, and query tools
```

---

Part of the Fels Public AI Lab MCP Servers project.
