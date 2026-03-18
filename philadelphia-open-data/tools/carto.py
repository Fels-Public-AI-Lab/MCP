"""
Philadelphia CARTO SQL API tools.

Provides schema inspection and read-only SQL query execution for Philadelphia
open data tables hosted on the City's CARTO instance (phl.carto.com).

Field dictionaries are loaded at startup from data/dictionaries/*.csv.
Each CSV maps to its CARTO table name (e.g. opa_properties_public.csv).
"""

from tools import mcp
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, Dict, Any
from enum import Enum
import httpx
import json
import re
import csv
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

CARTO_API_URL = "https://phl.carto.com/api/v2/sql"
CHARACTER_LIMIT = 25000
MAX_ROWS = 1000

# Known Philadelphia CARTO tables with human-readable descriptions.
# Add entries here as new tables are discovered.
KNOWN_TABLES: Dict[str, str] = {
    "public_cases_fc": "311 service requests — resident complaints and city service requests",
    "incidents_part1_part2": "Philadelphia Police crime incidents (Part I and Part II offenses)",
    "li_permits": "Licenses & Inspections building permits",
    "li_violations": "Licenses & Inspections code violations",
    "parking_violations": "Philadelphia Parking Authority parking violation notices",
    "opa_properties_public": "Office of Property Assessment — property records and valuations",
}


# ==================== DATA DICTIONARIES ====================

_DICT_DIR = Path(__file__).parent.parent / "data" / "dictionaries"
_HTML_TAG_RE = re.compile(r'<[^>]+>')


def _clean(text: str) -> str:
    """Strip HTML tags and collapse whitespace."""
    return re.sub(r'\s+', ' ', _HTML_TAG_RE.sub(' ', text or '')).strip()


def _parse_code_labels(description: str) -> Dict[str, str]:
    """
    Extract code→label mappings from OPA-style description text.

    Handles patterns like:
      "0. Not Applicable"
      "A. Full Finished – Occupies the entire area..."   → "Full Finished"
      "1. NEWER CONSTRUCTION – Noticeably newer..."      → "NEWER CONSTRUCTION"
      "a. Natural Gas"
      "c. Electric (usually in excess of 150 amps)"      → "Electric"

    Strategy: capture everything after the code up to the end of the segment,
    then truncate at the first em-dash / spaced hyphen / parenthesis,
    which separates the short label from the prose explanation.
    """
    codes: Dict[str, str] = {}
    # Match code patterns following newlines, HTML close-tags (>), or start of string
    for m in re.finditer(
        r'(?:^|[\n>])\s*([0-9a-zA-ZØ]+)\.\s+(.*?)(?=\s*(?:<|\n|$))',
        description,
        re.MULTILINE,
    ):
        code = m.group(1).strip()
        raw = m.group(2).strip()
        if not raw:
            continue
        # Truncate at em-dash, spaced hyphen/dash, or opening parenthetical
        label = re.split(r'\s+[–—]\s+|\s+-\s+|\s+\(', raw)[0].strip().rstrip('.,')
        # Skip codes that look like regular English words rather than categorical
        # codes — e.g. "Code" appearing in "City Code." mid-sentence.
        # Real codes are: single char (A, a, Ø), digits (0–9), or ALL-CAPS (NONE).
        if len(code) > 2 and code.isalpha() and not code.isupper():
            continue
        # Keep labels that are non-trivial but not so long they're prose sentences
        if 2 <= len(label) <= 50:
            codes[code] = label
    return codes


def _load_dictionaries() -> Dict[str, Dict[str, Dict]]:
    """
    Load all CSV dictionaries from data/dictionaries/.

    Returns:
        {
            table_name: {
                field_name_lower: {
                    "alias":       str,
                    "description": str (HTML-stripped, full text),
                    "codes":       {code: label} or {} if no coded values
                }
            }
        }
    """
    result: Dict[str, Dict[str, Dict]] = {}
    if not _DICT_DIR.exists():
        return result
    for csv_path in sorted(_DICT_DIR.glob("*.csv")):
        table = csv_path.stem
        fields: Dict[str, Dict] = {}
        try:
            with open(csv_path, newline='', encoding='utf-8-sig') as f:
                for row in csv.DictReader(f):
                    name = (row.get("Field Name") or "").strip().lower()
                    if not name:
                        continue
                    raw_desc = row.get("Description") or ""
                    desc = _clean(raw_desc)
                    fields[name] = {
                        "alias":       (row.get("Alias") or "").strip(),
                        "description": desc,
                        "codes":       _parse_code_labels(raw_desc),
                    }
        except Exception:
            pass
        result[table] = fields
    return result


# Loaded once at module import; shared by both tools.
DICTIONARIES: Dict[str, Dict[str, Dict]] = _load_dictionaries()


# ==================== RATE LIMITER ====================

class RateLimiter:
    def __init__(self, calls_per_minute: int = 60):
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


carto_rate_limiter = RateLimiter(60)


# ==================== HELPERS ====================

async def _execute_carto_sql(query: str) -> Dict[str, Any]:
    """Execute a SQL query against the Philadelphia CARTO API."""
    await carto_rate_limiter.wait_if_needed()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            CARTO_API_URL,
            params={"q": query, "format": "json"},
        )
        response.raise_for_status()
        return response.json()


def _handle_api_error(e: Exception) -> str:
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 429:
            return "⚠️ Rate limit exceeded. Please wait a moment and try again."
        elif e.response.status_code == 404:
            return "🔍 No data found. Verify the table name."
        elif e.response.status_code == 400:
            return f"❌ Invalid query: {e.response.text}"
    return f"❌ Error: {str(e)}"


_SAFE_TABLE_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')
_FORBIDDEN_SQL_RE = re.compile(
    r'\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT|REVOKE|EXECUTE|EXEC)\b',
    re.IGNORECASE,
)


# ==================== ENUMS ====================

class ResponseFormat(str, Enum):
    """Output format for responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# ==================== INPUT MODELS ====================

class CartoSchemaInput(BaseModel):
    """Get column schema for a Philadelphia CARTO table."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    table_name: str = Field(
        ...,
        description=(
            "CARTO table name. "
            f"Known tables: {', '.join(KNOWN_TABLES.keys())}"
        ),
        min_length=1,
        max_length=100,
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator('table_name')
    @classmethod
    def validate_table_name(cls, v):
        if not _SAFE_TABLE_RE.match(v):
            raise ValueError("Table name must contain only letters, digits, and underscores")
        return v.lower()


class CartoQueryInput(BaseModel):
    """Execute a SELECT query against a Philadelphia CARTO table."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    table_name: str = Field(
        ...,
        description=(
            "CARTO table to query. "
            f"Known tables: {', '.join(KNOWN_TABLES.keys())}"
        ),
        min_length=1,
        max_length=100,
    )
    sql: str = Field(
        ...,
        description=(
            "SQL WHERE clause (and optional ORDER BY / column list). "
            "Do not include SELECT ... FROM; the tool wraps your conditions. "
            "Example: \"status = 'Open' ORDER BY requested_datetime DESC\""
        ),
        max_length=2000,
    )
    limit: Optional[int] = Field(default=100, ge=1, le=MAX_ROWS)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator('table_name')
    @classmethod
    def validate_table_name(cls, v):
        if not _SAFE_TABLE_RE.match(v):
            raise ValueError("Table name must contain only letters, digits, and underscores")
        return v.lower()

    @field_validator('sql')
    @classmethod
    def must_be_select_safe(cls, v):
        if _FORBIDDEN_SQL_RE.search(v):
            raise ValueError("Only SELECT queries are permitted — no data modification allowed")
        return v


# ==================== TOOLS ====================

@mcp.tool(
    name="carto_get_schema",
    annotations={
        "title": "Get CARTO Table Schema",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def carto_get_schema(params: CartoSchemaInput) -> str:
    """
    Return column names and data types for a Philadelphia CARTO table.

    Uses SELECT * LIMIT 0 to read the 'fields' metadata from the CARTO
    SQL API response without transferring any rows. Use this before querying
    an unfamiliar table to understand available fields.
    """
    try:
        # CARTO SQL API returns a `fields` dict on every response:
        # {"rows": [], "fields": {"col": {"type": "string"}, ...}, "time": ...}
        # LIMIT 0 gives us the schema with zero data transfer.
        query = f"SELECT * FROM {params.table_name} LIMIT 0"

        result = await _execute_carto_sql(query)

        fields = result.get("fields") or {}
        if not fields:
            known = ", ".join(KNOWN_TABLES.keys())
            return f"No schema found for '{params.table_name}'. Known tables: {known}"

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "table": params.table_name,
                "description": KNOWN_TABLES.get(params.table_name, ""),
                "fields": fields,
            }, indent=2)

        table_desc = KNOWN_TABLES.get(params.table_name, "")
        dict_fields = DICTIONARIES.get(params.table_name, {})
        has_dict = bool(dict_fields)

        output = f"# Schema: `{params.table_name}`\n\n"
        if table_desc:
            output += f"**Description**: {table_desc}\n\n"
        if has_dict:
            output += "_Field descriptions from OpenDataPhilly metadata._\n\n"
        output += f"**Columns** ({len(fields)}):\n\n"

        if has_dict:
            output += "| Column | Type | Description |\n"
            output += "|--------|------|-------------|\n"
            for col_name, col_meta in fields.items():
                col_type = col_meta.get("type", "unknown") if isinstance(col_meta, dict) else str(col_meta)
                field_info = dict_fields.get(col_name.lower(), {})
                alias = field_info.get("alias", "")
                desc = field_info.get("description", "")
                # Show alias in parens if it differs from the column name
                label = f"{desc}"
                if alias and alias.lower() != col_name.lower():
                    label = f"**{alias}** — {desc}" if desc else alias
                # Truncate long descriptions so the table stays readable
                if len(label) > 120:
                    label = label[:117] + "..."
                output += f"| `{col_name}` | {col_type} | {label} |\n"
        else:
            output += "| Column | Type |\n"
            output += "|--------|------|\n"
            for col_name, col_meta in fields.items():
                col_type = col_meta.get("type", "unknown") if isinstance(col_meta, dict) else str(col_meta)
                output += f"| `{col_name}` | {col_type} |\n"

        return output

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="carto_query",
    annotations={
        "title": "Query Philadelphia CARTO Data",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def carto_query(params: CartoQueryInput) -> str:
    """
    Execute a read-only SELECT query against a Philadelphia CARTO open data table.

    Only SELECT statements are permitted. Maximum 1000 rows per call.
    Pass your WHERE clause (and optional ORDER BY) in the sql parameter;
    the tool wraps it in SELECT * FROM <table> WHERE ... LIMIT <n>.

    Known tables:
    - public_cases_fc: 311 service requests
    - incidents_part1_part2: crime incidents
    - li_permits: building permits
    - li_violations: code violations
    - parking_violations: PPA parking tickets
    - opa_properties_public: property assessments
    """
    try:
        sql_stripped = params.sql.strip()
        sql_upper = sql_stripped.upper()

        # If the caller passed a full SELECT, use it directly (still validated above)
        if sql_upper.startswith("SELECT"):
            full_query = f"{sql_stripped} LIMIT {params.limit}"
        else:
            full_query = (
                f"SELECT * FROM {params.table_name} "
                f"WHERE {sql_stripped} "
                f"LIMIT {params.limit}"
            )

        result = await _execute_carto_sql(full_query)

        if not result.get("rows"):
            return f"No rows returned from `{params.table_name}`."

        rows = result["rows"]
        query_time = result.get("time", "N/A")

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({
                "table": params.table_name,
                "row_count": len(rows),
                "query_time_ms": query_time,
                "rows": rows,
            }, indent=2)[:CHARACTER_LIMIT]

        output = f"# Query Results: `{params.table_name}`\n\n"
        output += f"**Rows returned**: {len(rows)}"
        if len(rows) == params.limit:
            output += " *(limit reached — refine query or increase limit)*"
        output += f" | **Query time**: {query_time}s\n\n"

        if rows:
            cols = list(rows[0].keys())
            dict_fields = DICTIONARIES.get(params.table_name, {})
            output += "| " + " | ".join(cols) + " |\n"
            output += "| " + " | ".join(["---"] * len(cols)) + " |\n"
            for row in rows:
                values = []
                for c in cols:
                    raw = str(row.get(c, "") or "")
                    # Inline decode: if this field has code labels and the
                    # raw value matches a code, append the label in parens.
                    field_info = dict_fields.get(c.lower(), {})
                    codes = field_info.get("codes", {})
                    if codes and raw in codes:
                        raw = f"{raw} ({codes[raw]})"
                    values.append(raw[:80].replace("|", "\\|"))
                output += "| " + " | ".join(values) + " |\n"

        return output[:CHARACTER_LIMIT]

    except Exception as e:
        return _handle_api_error(e)
