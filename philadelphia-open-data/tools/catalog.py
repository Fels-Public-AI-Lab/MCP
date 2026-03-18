"""
OpenDataPhilly catalog search tools.

Fetches and caches https://opendataphilly.org/datasets.json at startup,
then exposes search and detail tools for the MCP server.
"""

from tools import mcp
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Dict, Any
from enum import Enum
import httpx
import json
from datetime import datetime, timedelta
import asyncio

CATALOG_URL = "https://opendataphilly.org/datasets.json"
CHARACTER_LIMIT = 25000
CACHE_TTL_HOURS = 6


# ==================== RATE LIMITER ====================

class RateLimiter:
    def __init__(self, calls_per_minute: int = 30):
        self.calls_per_minute = calls_per_minute
        self.calls = []

    async def wait_if_needed(self):
        now = datetime.now()
        self.calls = [c for c in self.calls if now - c < timedelta(minutes=1)]
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0]).seconds
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        self.calls.append(now)


catalog_rate_limiter = RateLimiter(30)


# ==================== CATALOG CACHE ====================

_catalog_cache: Optional[List[Dict[str, Any]]] = None
_catalog_fetched_at: Optional[datetime] = None


async def _get_catalog() -> List[Dict[str, Any]]:
    """Fetch and cache the OpenDataPhilly datasets catalog."""
    global _catalog_cache, _catalog_fetched_at

    now = datetime.now()
    if (
        _catalog_cache is not None
        and _catalog_fetched_at is not None
        and now - _catalog_fetched_at < timedelta(hours=CACHE_TTL_HOURS)
    ):
        return _catalog_cache

    await catalog_rate_limiter.wait_if_needed()

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(CATALOG_URL)
        response.raise_for_status()
        data = response.json()

    # Normalize: datasets.json may return a list or a nested dict
    if isinstance(data, list):
        datasets = data
    elif isinstance(data, dict):
        datasets = data.get("result", data.get("results", data.get("datasets", [])))
        if isinstance(datasets, dict):
            datasets = datasets.get("results", [])
    else:
        datasets = []

    _catalog_cache = datasets
    _catalog_fetched_at = now
    return _catalog_cache


# ==================== HELPERS ====================

# Actual datasets.json schema (verified against live API):
#   title:          str
#   organization:   str  (plain string, not dict)
#   notes:          str  (HTML)
#   category:       list[str]
#   resource_names: str  (space-separated resource names)
#   tags:           str  (comma- or space-separated)
#   url:            str  ("/datasets/<slug>/")

def _handle_api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 429:
            return "⚠️ Rate limit exceeded. Please wait a moment and try again."
        elif e.response.status_code == 404:
            return "🔍 Catalog endpoint not found."
        elif e.response.status_code == 400:
            return f"❌ Invalid request: {e.response.text}"
    return f"❌ Error: {str(e)}"


def _org_name(ds: Dict[str, Any]) -> str:
    """organization is a plain string in datasets.json."""
    return str(ds.get("organization") or "")


def _tag_string(ds: Dict[str, Any]) -> str:
    """tags is a plain string in datasets.json."""
    return str(ds.get("tags") or "").lower()


def _slug(ds: Dict[str, Any]) -> str:
    """Extract slug from url field: '/datasets/crime-incidents/' -> 'crime-incidents'."""
    url = ds.get("url") or ""
    return url.strip("/").split("/")[-1]


def _dataset_url(ds: Dict[str, Any]) -> str:
    """Full OpenDataPhilly page URL for this dataset."""
    url = ds.get("url") or ""
    if url.startswith("http"):
        return url
    return f"https://opendataphilly.org{url}"


# ==================== ENUMS ====================

class ResponseFormat(str, Enum):
    """Output format for responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ==================== INPUT MODELS ====================

class SearchCatalogInput(BaseModel):
    """Search the OpenDataPhilly dataset catalog by keyword."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    query: str = Field(
        ...,
        description="Search terms matched against dataset title, description, and tags",
        min_length=1,
        max_length=200,
    )
    category: Optional[str] = Field(
        default=None,
        description="Filter by category/group name (partial match)",
        max_length=100,
    )
    organization: Optional[str] = Field(
        default=None,
        description="Filter by publishing organization name (partial match)",
        max_length=100,
    )
    limit: Optional[int] = Field(default=10, ge=1, le=50)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class DatasetDetailsInput(BaseModel):
    """Get full metadata for a single OpenDataPhilly dataset."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    title_or_slug: str = Field(
        ...,
        description="Dataset title (partial match) or exact URL slug",
        min_length=1,
        max_length=200,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ==================== TOOLS ====================

@mcp.tool(
    name="catalog_search",
    annotations={
        "title": "Search OpenDataPhilly Catalog",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def catalog_search(params: SearchCatalogInput) -> str:
    """
    Search the OpenDataPhilly dataset catalog by keyword.

    Searches across dataset titles, descriptions (notes), and tags.
    Optionally filter by category or publishing organization.
    Returns matching datasets with resource download URLs.
    """
    try:
        datasets = await _get_catalog()
        query_lower = params.query.lower()
        matches = []

        for ds in datasets:
            title = (ds.get("title") or "").lower()
            notes = (ds.get("notes") or "").lower()
            tags = _tag_string(ds)

            if query_lower not in title and query_lower not in notes and query_lower not in tags:
                continue

            if params.category:
                # category is a list[str] in datasets.json
                cats = ds.get("category") or []
                if not any(params.category.lower() in c.lower() for c in cats):
                    continue

            if params.organization:
                if params.organization.lower() not in _org_name(ds).lower():
                    continue

            matches.append(ds)
            if len(matches) >= params.limit:
                break

        if not matches:
            return f"No datasets found matching '{params.query}'."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(matches), "datasets": matches}, indent=2)[:CHARACTER_LIMIT]

        output = f"# OpenDataPhilly Search Results\n\n"
        output += f"**Query**: {params.query} | **Found**: {len(matches)} dataset(s)\n\n"

        for i, ds in enumerate(matches, 1):
            title = ds.get("title") or "Untitled"
            output += f"## {i}. {title}\n"

            org = _org_name(ds)
            if org:
                output += f"- **Organization**: {org}\n"

            cats = ds.get("category") or []
            if cats:
                output += f"- **Categories**: {', '.join(cats)}\n"

            notes = ds.get("notes") or ""
            if notes:
                # Strip HTML tags for a plain-text snippet
                import re
                plain = re.sub(r'<[^>]+>', '', notes).strip()
                snippet = plain[:200] + "..." if len(plain) > 200 else plain
                output += f"- **Description**: {snippet}\n"

            resource_names = ds.get("resource_names") or ""
            if resource_names:
                output += f"- **Resources**: {resource_names[:200]}\n"

            output += f"- **Page**: {_dataset_url(ds)}\n"
            output += f"- **Slug**: `{_slug(ds)}`\n"
            output += "\n"

        return output[:CHARACTER_LIMIT]

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="catalog_get_dataset",
    annotations={
        "title": "Get Dataset Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def catalog_get_dataset(params: DatasetDetailsInput) -> str:
    """
    Get full metadata for a single OpenDataPhilly dataset.

    Matches by title (partial) or exact URL slug. Returns all available
    metadata including all resource URLs, tags, categories, and update frequency.
    """
    try:
        datasets = await _get_catalog()
        search_term = params.title_or_slug.lower()
        match = None

        # Priority: exact slug match > exact title > title contains > partial slug
        for ds in datasets:
            ds_slug = _slug(ds).lower()
            ds_title = (ds.get("title") or "").lower()
            if search_term == ds_slug or search_term == ds_title:
                match = ds
                break

        if not match:
            for ds in datasets:
                ds_title = (ds.get("title") or "").lower()
                if search_term in ds_title:
                    match = ds
                    break

        if not match:
            for ds in datasets:
                ds_slug = _slug(ds).lower()
                if search_term in ds_slug:
                    match = ds
                    break

        if not match:
            return f"No dataset found matching '{params.title_or_slug}'."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"dataset": match}, indent=2)[:CHARACTER_LIMIT]

        import re
        title = match.get("title") or "Untitled"
        output = f"# {title}\n\n"

        org = _org_name(match)
        if org:
            output += f"**Organization**: {org}\n"

        cats = match.get("category") or []
        if cats:
            output += f"**Categories**: {', '.join(cats)}\n"

        tags = _tag_string(match)
        if tags.strip():
            output += f"**Tags**: {tags}\n"

        output += f"**Page**: {_dataset_url(match)}\n"
        output += f"**Slug**: `{_slug(match)}`\n\n"

        notes = match.get("notes") or ""
        if notes:
            plain = re.sub(r'<[^>]+>', '', notes).strip()
            output += f"## Description\n{plain}\n\n"

        resource_names = match.get("resource_names") or ""
        if resource_names:
            output += f"## Resources\n{resource_names}\n\n"

        return output[:CHARACTER_LIMIT]

    except Exception as e:
        return _handle_api_error(e)
