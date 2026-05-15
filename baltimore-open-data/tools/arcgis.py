"""
Baltimore ArcGIS REST API tools.

The City of Baltimore publishes open data through ArcGIS REST services. This
module exposes read-only catalog, schema, and query helpers over:
  - https://opendata.baltimorecity.gov/egis/rest/services
  - https://geodata.baltimorecity.gov/egis/rest/services

All tools use public endpoints and do not require authentication.
"""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator

from tools import mcp

CHARACTER_LIMIT = 25000
CACHE_TTL_HOURS = 6
DEFAULT_TIMEOUT = 30.0
MAX_ROWS = 2000

ARCGIS_ROOTS: Dict[str, str] = {
    "open_data": "https://opendata.baltimorecity.gov/egis/rest/services",
    "geodata": "https://geodata.baltimorecity.gov/egis/rest/services",
    "egisdata": "https://egisdata.baltimorecity.gov/egis/rest/services",
    "egis": "https://egis.baltimorecity.gov/egis/rest/services",
    "arcgis_online": "https://services1.arcgis.com/UWYHeuuJISiGmgXx/arcgis/rest/services",
}

SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9_\- /]+$")
FORBIDDEN_WHERE_RE = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXECUTE|EXEC|MERGE)\b",
    re.IGNORECASE,
)


class RateLimiter:
    def __init__(self, calls_per_minute: int = 90):
        self.calls_per_minute = calls_per_minute
        self.calls: List[datetime] = []

    async def wait_if_needed(self) -> None:
        now = datetime.now()
        self.calls = [c for c in self.calls if now - c < timedelta(minutes=1)]
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0]).seconds
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self.calls.append(now)


arcgis_rate_limiter = RateLimiter()

_catalog_cache: Optional[List[Dict[str, Any]]] = None
_catalog_fetched_at: Optional[datetime] = None
_service_cache: Dict[str, Dict[str, Any]] = {}
_layer_cache: Dict[str, Dict[str, Any]] = {}


class ResponseFormat(str, Enum):
    MARKDOWN = "markdown"
    JSON = "json"


class ServiceType(str, Enum):
    FEATURE_SERVER = "FeatureServer"
    MAP_SERVER = "MapServer"


class CatalogSearchInput(BaseModel):
    """Search Baltimore ArcGIS service metadata."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    query: str = Field(
        ...,
        description="Search terms matched against service names, folders, descriptions, keywords, and layer names.",
        min_length=1,
        max_length=200,
    )
    root: Optional[str] = Field(
        default=None,
        description="Optional root filter: open_data, geodata, egisdata, egis, or arcgis_online. Searches all when omitted.",
    )
    folder: Optional[str] = Field(
        default=None,
        description="Optional ArcGIS folder filter, such as Hosted, CityView, Housing, Planning, or DOF.",
        max_length=100,
    )
    service_type: Optional[ServiceType] = Field(
        default=None,
        description="Optional service type filter. FeatureServer is best for row-level dataset queries.",
    )
    limit: int = Field(default=10, ge=1, le=50)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator("root")
    @classmethod
    def validate_root(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ARCGIS_ROOTS:
            raise ValueError(f"root must be one of: {', '.join(ARCGIS_ROOTS)}")
        return v


class ServiceInput(BaseModel):
    """Get details for one Baltimore ArcGIS service."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    service_path: str = Field(
        ...,
        description="ArcGIS service path without the service type, e.g. Hosted/Restaurants or CityView/Realproperty_OB.",
        min_length=1,
        max_length=250,
    )
    service_type: ServiceType = Field(default=ServiceType.FEATURE_SERVER)
    root: str = Field(default="geodata", description="ArcGIS root: open_data, geodata, egisdata, egis, or arcgis_online.")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator("service_path")
    @classmethod
    def validate_service_path(cls, v: str) -> str:
        return _validate_path(v, "service_path")

    @field_validator("root")
    @classmethod
    def validate_root(cls, v: str) -> str:
        if v not in ARCGIS_ROOTS:
            raise ValueError(f"root must be one of: {', '.join(ARCGIS_ROOTS)}")
        return v


class LayerSchemaInput(ServiceInput):
    """Get field metadata for one layer or table in a Baltimore ArcGIS service."""

    layer_id: int = Field(default=0, ge=0, le=999)


class QueryLayerInput(LayerSchemaInput):
    """Query rows from one Baltimore ArcGIS feature layer or map layer."""

    where: str = Field(
        default="1=1",
        description="ArcGIS SQL WHERE clause. Example: \"ZIPCODE = '21201'\". Only read-only queries are allowed.",
        max_length=2000,
    )
    out_fields: str = Field(
        default="*",
        description="Comma-separated output fields, or * for all fields.",
        max_length=1000,
    )
    order_by_fields: Optional[str] = Field(
        default=None,
        description="Optional ArcGIS orderByFields value, e.g. OBJECTID DESC.",
        max_length=500,
    )
    result_offset: int = Field(default=0, ge=0, le=100000)
    limit: int = Field(default=100, ge=1, le=MAX_ROWS)
    return_geometry: bool = Field(default=False)
    out_sr: Optional[int] = Field(
        default=4326,
        description="Output spatial reference WKID for returned geometry. Use 4326 for lon/lat.",
        ge=1,
        le=100000,
    )

    @field_validator("where")
    @classmethod
    def validate_where(cls, v: str) -> str:
        if FORBIDDEN_WHERE_RE.search(v):
            raise ValueError("Only read-only WHERE clauses are permitted.")
        return v

    @field_validator("out_fields", "order_by_fields")
    @classmethod
    def validate_sql_fragment(cls, v: Optional[str]) -> Optional[str]:
        if v and FORBIDDEN_WHERE_RE.search(v):
            raise ValueError("Only read-only query fragments are permitted.")
        return v


def _validate_path(value: str, field_name: str) -> str:
    normalized = value.strip().strip("/")
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    if not SAFE_PATH_RE.match(normalized):
        raise ValueError(f"{field_name} contains unsupported characters")
    if ".." in normalized:
        raise ValueError(f"{field_name} cannot contain '..'")
    return normalized


def _service_url(root: str, service_path: str, service_type: ServiceType | str) -> str:
    return f"{ARCGIS_ROOTS[root]}/{service_path}/{_service_type_value(service_type)}"


def _layer_url(root: str, service_path: str, service_type: ServiceType | str, layer_id: int) -> str:
    return f"{_service_url(root, service_path, service_type)}/{layer_id}"


def _service_type_value(service_type: ServiceType | str) -> str:
    if isinstance(service_type, ServiceType):
        return service_type.value
    return str(service_type)


async def _arcgis_get(url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    await arcgis_rate_limiter.wait_if_needed()
    request_params = {"f": "json"}
    if params:
        request_params.update(params)
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        response = await client.get(url, params=request_params)
        response.raise_for_status()
        data = response.json()
    if isinstance(data, dict) and "error" in data:
        message = data["error"].get("message", "ArcGIS error")
        details = data["error"].get("details") or []
        raise ValueError(f"{message}: {'; '.join(details)}")
    return data


async def _get_catalog() -> List[Dict[str, Any]]:
    global _catalog_cache, _catalog_fetched_at

    now = datetime.now()
    if (
        _catalog_cache is not None
        and _catalog_fetched_at is not None
        and now - _catalog_fetched_at < timedelta(hours=CACHE_TTL_HOURS)
    ):
        return _catalog_cache

    services: List[Dict[str, Any]] = []
    for root_name, root_url in ARCGIS_ROOTS.items():
        try:
            root_catalog = await _arcgis_get(root_url)
        except Exception:
            continue
        folders = root_catalog.get("folders") or []
        for service in root_catalog.get("services") or []:
            services.append(_catalog_entry(root_name, service))

        for folder in folders:
            try:
                folder_catalog = await _arcgis_get(f"{root_url}/{folder}")
            except Exception:
                continue
            for service in folder_catalog.get("services") or []:
                services.append(_catalog_entry(root_name, service, folder=folder))

    _catalog_cache = services
    _catalog_fetched_at = now
    return _catalog_cache


def _catalog_entry(root_name: str, service: Dict[str, Any], folder: Optional[str] = None) -> Dict[str, Any]:
    raw_name = service.get("name") or ""
    path = raw_name
    if folder and not raw_name.startswith(f"{folder}/"):
        path = f"{folder}/{raw_name}"
    short_name = path.split("/")[-1]
    return {
        "root": root_name,
        "folder": folder or "",
        "name": short_name,
        "path": path,
        "type": service.get("type") or "",
        "url": f"{ARCGIS_ROOTS[root_name]}/{path}/{service.get('type')}",
    }


async def _get_service_metadata(root: str, service_path: str, service_type: ServiceType | str) -> Dict[str, Any]:
    cache_key = f"{root}:{service_path}:{service_type}"
    if cache_key not in _service_cache:
        _service_cache[cache_key] = await _arcgis_get(_service_url(root, service_path, service_type))
    return _service_cache[cache_key]


async def _enrich_catalog_entry(entry: Dict[str, Any]) -> Dict[str, Any]:
    if entry.get("_enriched"):
        return entry
    if entry["type"] not in {ServiceType.FEATURE_SERVER.value, ServiceType.MAP_SERVER.value}:
        entry["_enriched"] = True
        return entry
    meta = await _get_service_metadata(entry["root"], entry["path"], entry["type"])
    entry.update(
        {
            "service_description": meta.get("serviceDescription") or meta.get("description") or "",
            "copyright_text": meta.get("copyrightText") or "",
            "document_info": meta.get("documentInfo") or {},
            "layers": [
                {"id": layer.get("id"), "name": layer.get("name")}
                for layer in meta.get("layers", [])
            ],
            "tables": [
                {"id": table.get("id"), "name": table.get("name")}
                for table in meta.get("tables", [])
            ],
            "max_record_count": meta.get("maxRecordCount"),
            "_enriched": True,
        }
    )
    return entry


async def _get_layer_metadata(
    root: str,
    service_path: str,
    service_type: ServiceType | str,
    layer_id: int,
) -> Dict[str, Any]:
    cache_key = f"{root}:{service_path}:{service_type}:{layer_id}"
    if cache_key not in _layer_cache:
        _layer_cache[cache_key] = await _arcgis_get(_layer_url(root, service_path, service_type, layer_id))
    return _layer_cache[cache_key]


def _search_blob(entry: Dict[str, Any]) -> str:
    doc = entry.get("document_info") or {}
    pieces = [
        entry.get("root", ""),
        entry.get("folder", ""),
        entry.get("name", ""),
        entry.get("path", ""),
        entry.get("type", ""),
        entry.get("service_description", ""),
        entry.get("copyright_text", ""),
        doc.get("Title", ""),
        doc.get("Subject", ""),
        doc.get("Comments", ""),
        doc.get("Keywords", ""),
    ]
    pieces.extend(layer.get("name", "") for layer in entry.get("layers", []))
    pieces.extend(table.get("name", "") for table in entry.get("tables", []))
    return " ".join(str(p) for p in pieces if p).lower()


def _handle_api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 404:
            return "No ArcGIS resource found. Check the root, service_path, service_type, and layer_id."
        if e.response.status_code == 400:
            return f"Invalid ArcGIS request: {e.response.text}"
        if e.response.status_code == 429:
            return "Rate limit exceeded. Please wait a moment and try again."
    return f"Error: {str(e)}"


def _format_service_summary(entry: Dict[str, Any]) -> str:
    layers = entry.get("layers") or []
    tables = entry.get("tables") or []
    output = f"## {entry.get('path')} ({entry.get('type')})\n"
    output += f"- Root: `{entry.get('root')}`\n"
    if entry.get("folder"):
        output += f"- Folder: {entry.get('folder')}\n"
    desc = entry.get("service_description") or ""
    if desc:
        output += f"- Description: {str(desc)[:300]}\n"
    doc = entry.get("document_info") or {}
    keywords = doc.get("Keywords")
    if keywords:
        output += f"- Keywords: {keywords}\n"
    if layers:
        layer_text = ", ".join(f"{l.get('name')} ({l.get('id')})" for l in layers[:10])
        output += f"- Layers: {layer_text}\n"
    if tables:
        table_text = ", ".join(f"{t.get('name')} ({t.get('id')})" for t in tables[:10])
        output += f"- Tables: {table_text}\n"
    output += f"- URL: {entry.get('url')}\n"
    output += "\n"
    return output


@mcp.tool(
    name="baltimore_catalog_search",
    annotations={
        "title": "Search Baltimore ArcGIS Catalog",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def baltimore_catalog_search(params: CatalogSearchInput) -> str:
    """
    Search Baltimore's ArcGIS Open Data and Enterprise GIS service catalogs.

    Use this first to discover service paths and layer IDs before querying data.
    """
    try:
        catalog = await _get_catalog()
        query = params.query.lower()
        matches: List[Dict[str, Any]] = []

        candidates: List[Dict[str, Any]] = []
        for entry in catalog:
            if params.root and entry.get("root") != params.root:
                continue
            if params.folder and params.folder.lower() not in (entry.get("folder") or "").lower():
                continue
            if params.service_type and entry.get("type") != params.service_type.value:
                continue
            candidates.append(entry)

        # Fast path: match service names and folders from the catalog listing,
        # then enrich those matches for descriptions, layers, and URLs.
        for entry in candidates:
            if query not in _search_blob(entry):
                continue
            try:
                entry = await _enrich_catalog_entry(entry)
            except Exception:
                pass
            matches.append(entry)
            if len(matches) >= params.limit:
                break

        # Slower path: if name/folder matching did not fill the request, fetch
        # service metadata lazily so searches can hit keywords and layer names.
        if len(matches) < params.limit:
            matched_paths = {entry.get("url") for entry in matches}
            for entry in candidates:
                if entry.get("url") in matched_paths:
                    continue
                try:
                    entry = await _enrich_catalog_entry(entry)
                except Exception:
                    continue
                if query not in _search_blob(entry):
                    continue
                matches.append(entry)
                if len(matches) >= params.limit:
                    break

        if not matches:
            return f"No Baltimore ArcGIS services found matching '{params.query}'."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(matches), "services": matches}, indent=2)[:CHARACTER_LIMIT]

        output = "# Baltimore ArcGIS Catalog Search Results\n\n"
        output += f"Query: `{params.query}` | Found: {len(matches)} service(s)\n\n"
        for entry in matches:
            output += _format_service_summary(entry)
        return output[:CHARACTER_LIMIT]
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="baltimore_get_service",
    annotations={
        "title": "Get Baltimore ArcGIS Service Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def baltimore_get_service(params: ServiceInput) -> str:
    """Get metadata, layers, tables, extents, and capabilities for one ArcGIS service."""
    try:
        metadata = await _get_service_metadata(params.root, params.service_path, params.service_type)
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(metadata, indent=2)[:CHARACTER_LIMIT]

        output = f"# {params.service_path} ({_service_type_value(params.service_type)})\n\n"
        desc = metadata.get("serviceDescription") or metadata.get("description")
        if desc:
            output += f"**Description**: {desc}\n\n"
        output += f"**Root**: `{params.root}`\n"
        output += f"**URL**: {_service_url(params.root, params.service_path, params.service_type)}\n"
        if metadata.get("maxRecordCount"):
            output += f"**Max record count**: {metadata.get('maxRecordCount')}\n"
        if metadata.get("supportedQueryFormats"):
            output += f"**Supported query formats**: {metadata.get('supportedQueryFormats')}\n"
        output += "\n"

        layers = metadata.get("layers") or []
        if layers:
            output += "## Layers\n\n| ID | Name |\n|---:|------|\n"
            for layer in layers:
                output += f"| {layer.get('id')} | {layer.get('name')} |\n"
            output += "\n"

        tables = metadata.get("tables") or []
        if tables:
            output += "## Tables\n\n| ID | Name |\n|---:|------|\n"
            for table in tables:
                output += f"| {table.get('id')} | {table.get('name')} |\n"
            output += "\n"

        doc = metadata.get("documentInfo") or {}
        if doc:
            output += "## Document Info\n\n"
            for key in ("Title", "Subject", "Comments", "Keywords", "Author"):
                if doc.get(key):
                    output += f"- **{key}**: {doc.get(key)}\n"

        return output[:CHARACTER_LIMIT]
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="baltimore_get_layer_schema",
    annotations={
        "title": "Get Baltimore ArcGIS Layer Schema",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def baltimore_get_layer_schema(params: LayerSchemaInput) -> str:
    """Return field names, aliases, types, geometry type, and capabilities for one layer."""
    try:
        metadata = await _get_layer_metadata(
            params.root,
            params.service_path,
            params.service_type,
            params.layer_id,
        )
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(metadata, indent=2)[:CHARACTER_LIMIT]

        output = (
            f"# Schema: "
            f"{params.service_path}/{_service_type_value(params.service_type)}/{params.layer_id}\n\n"
        )
        output += f"**Layer name**: {metadata.get('name', '')}\n"
        if metadata.get("type"):
            output += f"**Type**: {metadata.get('type')}\n"
        if metadata.get("geometryType"):
            output += f"**Geometry**: {metadata.get('geometryType')}\n"
        if metadata.get("objectIdField"):
            output += f"**Object ID field**: `{metadata.get('objectIdField')}`\n"
        if metadata.get("displayField"):
            output += f"**Display field**: `{metadata.get('displayField')}`\n"
        if metadata.get("maxRecordCount"):
            output += f"**Max record count**: {metadata.get('maxRecordCount')}\n"
        output += f"**URL**: {_layer_url(params.root, params.service_path, params.service_type, params.layer_id)}\n\n"

        fields = metadata.get("fields") or []
        output += f"## Fields ({len(fields)})\n\n"
        output += "| Name | Alias | Type | Length |\n|------|-------|------|-------:|\n"
        for field in fields:
            output += (
                f"| `{field.get('name')}` | {field.get('alias', '')} | "
                f"{field.get('type', '')} | {field.get('length', '')} |\n"
            )
        return output[:CHARACTER_LIMIT]
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="baltimore_query_layer",
    annotations={
        "title": "Query Baltimore ArcGIS Layer",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    },
)
async def baltimore_query_layer(params: QueryLayerInput) -> str:
    """
    Query rows from a Baltimore ArcGIS layer using a read-only WHERE clause.

    Use baltimore_get_layer_schema first to learn field names and types.
    """
    try:
        query_params: Dict[str, Any] = {
            "where": params.where,
            "outFields": params.out_fields,
            "returnGeometry": str(params.return_geometry).lower(),
            "resultOffset": params.result_offset,
            "resultRecordCount": params.limit,
        }
        if params.order_by_fields:
            query_params["orderByFields"] = params.order_by_fields
        if params.return_geometry and params.out_sr:
            query_params["outSR"] = params.out_sr

        data = await _arcgis_get(
            f"{_layer_url(params.root, params.service_path, params.service_type, params.layer_id)}/query",
            query_params,
        )

        features = data.get("features") or []
        if params.response_format == ResponseFormat.JSON:
            return json.dumps(
                {
                    "service_path": params.service_path,
                    "service_type": _service_type_value(params.service_type),
                    "layer_id": params.layer_id,
                    "row_count": len(features),
                    "exceeded_transfer_limit": data.get("exceededTransferLimit", False),
                    "features": features,
                },
                indent=2,
            )[:CHARACTER_LIMIT]

        if not features:
            return f"No rows returned from `{params.service_path}` layer {params.layer_id}."

        rows = [feature.get("attributes", {}) for feature in features]
        columns: List[str] = []
        for row in rows:
            for column in row:
                if column not in columns:
                    columns.append(column)

        output = (
            f"# Query Results: "
            f"{params.service_path}/{_service_type_value(params.service_type)}/{params.layer_id}\n\n"
        )
        output += f"Rows returned: {len(rows)}"
        if data.get("exceededTransferLimit"):
            output += " (transfer limit exceeded; narrow the query or page with result_offset)"
        output += "\n\n"

        output += "| " + " | ".join(columns) + " |\n"
        output += "| " + " | ".join(["---"] * len(columns)) + " |\n"
        for row in rows:
            values = []
            for column in columns:
                value = row.get(column, "")
                if value is None:
                    value = ""
                values.append(str(value)[:120].replace("|", "\\|").replace("\n", " "))
            output += "| " + " | ".join(values) + " |\n"

        return output[:CHARACTER_LIMIT]
    except Exception as e:
        return _handle_api_error(e)
