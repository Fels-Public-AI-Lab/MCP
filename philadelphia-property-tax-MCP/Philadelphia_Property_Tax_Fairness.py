"""
Philadelphia Property Assessment & Census Data MCP Server - METADATA-DRIVEN VERSION

This version uses the actual CARTO API metadata to provide accurate field names,
descriptions, and validation.

Properties Table: 72 fields from Tax_fields.json
Assessment History Table: 7 fields from history_fields.json
Permits Table: 44 fields from fields.json
"""

from fastmcp import FastMCP
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional, List, Dict, Any, Literal
from enum import Enum
import httpx
import json
import os
from pathlib import Path
from datetime import datetime, timedelta
import asyncio

# Load environment variables
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / '.env'
    load_dotenv(dotenv_path=env_path)
except ImportError:
    pass

# Constants
API_BASE_URL = "https://phl.carto.com/api/v2/sql"
CENSUS_API_BASE_URL = "https://api.census.gov/data"
CHARACTER_LIMIT = 25000
DEFAULT_LIMIT = 20
MAX_LIMIT = 100

# Environment config
DEFAULT_CENSUS_API_KEY = os.getenv('CENSUS_API_KEY')
DEFAULT_CENSUS_YEAR = int(os.getenv('DEFAULT_CENSUS_YEAR', '2022'))
DEFAULT_CENSUS_DATASET = os.getenv('DEFAULT_CENSUS_DATASET', 'acs/acs5')

# Initialize FastMCP
mcp = FastMCP("philadelphia_property_census_mcp")


# ==================== ENUMS FROM METADATA ====================

class ResponseFormat(str, Enum):
    """Output format for responses."""
    MARKDOWN = "markdown"
    JSON = "json"


class CategoryCode(str, Enum):
    """Property category codes."""
    RESIDENTIAL = "1"
    HOTELS_APARTMENTS = "2"
    STORE_WITH_DWELLING = "3"
    COMMERCIAL = "4"
    INDUSTRIAL = "5"
    VACANT_LAND = "6"


class BasementType(str, Enum):
    """Basement types."""
    NONE = "0"
    FULL_FINISHED = "A"
    FULL_SEMI_FINISHED = "B"
    FULL_UNFINISHED = "C"
    FULL_UNKNOWN_FINISH = "D"
    PARTIAL_FINISHED = "E"
    PARTIAL_SEMI_FINISHED = "F"
    PARTIAL_UNFINISHED = "G"
    PARTIAL_UNKNOWN_FINISH = "H"
    UNKNOWN_SIZE_FINISHED = "I"
    UNKNOWN_SIZE_UNFINISHED = "J"


class ExteriorCondition(str, Enum):
    """Exterior condition codes."""
    NOT_APPLICABLE = "0"
    NEWER_CONSTRUCTION = "1"
    REHABILITATED = "2"
    ABOVE_AVERAGE = "3"
    AVERAGE = "4"
    BELOW_AVERAGE = "5"
    VACANT = "6"
    SEALED_CONDEMNED = "7"


class QualityGrade(str, Enum):
    """Quality grade codes."""
    LOW = "1"
    BELOW_AVERAGE = "2"
    AVERAGE = "3"
    ABOVE_AVERAGE = "4"
    EXCELLENT = "5"


class GarageType(str, Enum):
    """Garage type codes."""
    NONE = "0"
    ATTACHED = "A"
    DETACHED = "B"
    BUILT_IN = "C"
    CARPORT = "D"


class HeaterType(str, Enum):
    """Heater type codes."""
    NONE = "0"
    HOT_AIR = "A"
    HOT_WATER = "B"
    ELECTRIC_BASEBOARD = "C"
    HEAT_PUMP = "D"
    OTHER = "E"
    RADIANT = "G"
    UNDETERMINED = "H"


class FuelType(str, Enum):
    """Fuel type codes."""
    NATURAL_GAS = "A"
    OIL = "B"
    ELECTRIC = "C"
    COAL = "D"
    SOLAR = "E"
    OTHER = "F"
    NONE = "0"


class PermitStatus(str, Enum):
    """Permit status codes."""
    ISSUED = "ISSUED"
    COMPLETED = "COMPLETED"
    APPROVED = "APPROVED"
    IN_REVIEW = "IN REVIEW"
    CANCELLED = "CANCELLED"


class CensusDataset(str, Enum):
    """Census dataset types."""
    ACS5 = "acs/acs5"
    ACS1 = "acs/acs1"
    DECENNIAL = "dec/pl"


# ==================== RATE LIMITER ====================

class RateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    async def wait_if_needed(self):
        now = datetime.now()
        self.calls = [call for call in self.calls 
                     if now - call < timedelta(minutes=1)]
        
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0]).seconds
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)
        
        self.calls.append(now)

property_rate_limiter = RateLimiter(60)
census_rate_limiter = RateLimiter(60)


# ==================== INPUT MODELS ====================

class AssessmentSearchInput(BaseModel):
    """Search property assessment history (assessments table)."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    parcel_number: Optional[str] = Field(
        default=None,
        description="9-digit parcel identifier",
        min_length=5,
        max_length=20
    )
    year: Optional[int] = Field(
        default=None,
        description="Assessment year",
        ge=1900,
        le=2030
    )
    min_market_value: Optional[int] = Field(default=None, description="Minimum market value", ge=0)
    max_market_value: Optional[int] = Field(default=None, description="Maximum market value", ge=0)
    limit: Optional[int] = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    offset: Optional[int] = Field(default=0, ge=0)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator('parcel_number')
    @classmethod
    def clean_parcel(cls, v):
        return v.replace('-', '').replace(' ', '') if v else None


class PropertySearchInput(BaseModel):
    """Search properties by basic criteria."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    address: Optional[str] = Field(default=None, description="Street address", max_length=200)
    parcel_number: Optional[str] = Field(default=None, description="Parcel number", min_length=5, max_length=20)
    zip_code: Optional[str] = Field(default=None, description="5-digit ZIP code", min_length=5, max_length=5)
    limit: Optional[int] = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator('parcel_number')
    @classmethod
    def clean_parcel(cls, v):
        return v.replace('-', '').replace(' ', '') if v else None
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v):
        if v and not v.startswith('19'):
            raise ValueError("Philadelphia ZIP codes start with '19'")
        return v


class PropertyCharacteristicsInput(BaseModel):
    """Search properties by detailed characteristics."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    # Basic filters
    zip_code: Optional[str] = Field(default=None, min_length=5, max_length=5)
    category_code: Optional[CategoryCode] = Field(default=None, description="Property category")
    
    # Physical characteristics
    min_bedrooms: Optional[int] = Field(default=None, ge=0)
    max_bedrooms: Optional[int] = Field(default=None, ge=0)
    min_bathrooms: Optional[float] = Field(default=None, ge=0)
    max_bathrooms: Optional[float] = Field(default=None, ge=0)
    min_total_area: Optional[int] = Field(default=None, ge=0, description="Minimum total area in sq ft")
    max_total_area: Optional[int] = Field(default=None, ge=0, description="Maximum total area in sq ft")
    min_year_built: Optional[int] = Field(default=None, ge=1600, le=2030)
    max_year_built: Optional[int] = Field(default=None, ge=1600, le=2030)
    
    # Quality and condition
    quality_grade: Optional[QualityGrade] = Field(default=None)
    exterior_condition: Optional[ExteriorCondition] = Field(default=None)
    
    # Features
    basement_type: Optional[BasementType] = Field(default=None)
    garage_type: Optional[GarageType] = Field(default=None)
    central_air: Optional[Literal["Y", "N"]] = Field(default=None, description="Has central air")
    fireplaces: Optional[int] = Field(default=None, ge=0, description="Number of fireplaces")
    
    # Value
    min_market_value: Optional[int] = Field(default=None, ge=0)
    max_market_value: Optional[int] = Field(default=None, ge=0)
    
    limit: Optional[int] = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class PropertyDetailsInput(BaseModel):
    """Get complete property details."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    parcel_number: str = Field(..., description="9-digit parcel number", min_length=5, max_length=20)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator('parcel_number')
    @classmethod
    def clean_parcel(cls, v):
        return v.replace('-', '').replace(' ', '')


class PropertySalesInput(BaseModel):
    """Search recent property sales."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    zip_code: Optional[str] = Field(default=None, min_length=5, max_length=5)
    min_sale_price: Optional[int] = Field(default=None, ge=0)
    max_sale_price: Optional[int] = Field(default=None, ge=0)
    months_back: Optional[int] = Field(default=6, ge=1, le=60, description="How many months back to search")
    limit: Optional[int] = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class CensusDemographicsInput(BaseModel):
    """Census demographic query."""
    model_config = ConfigDict(extra='forbid')
    
    state_fips: str = Field(..., description="State FIPS (e.g., '42' for PA)")
    county_fips: Optional[str] = Field(default=None, description="County FIPS (e.g., '101' for Philadelphia)")
    zip_code: Optional[str] = Field(default=None, description="ZIP Code")
    year: int = Field(default=DEFAULT_CENSUS_YEAR, ge=2010, le=2030)
    dataset: CensusDataset = Field(default=CensusDataset.ACS5)
    api_key: Optional[str] = Field(default=DEFAULT_CENSUS_API_KEY)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class PermitSearchInput(BaseModel):
    """Search building permits."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')

    address: Optional[str] = Field(default=None, description="Street address", max_length=200)
    permit_number: Optional[str] = Field(default=None, description="Permit number", max_length=50)
    opa_account_num: Optional[str] = Field(default=None, description="OPA account number", max_length=20)
    permit_type: Optional[str] = Field(default=None, description="Permit type (e.g., BUILDING, DEMOLITION, ZONING)")
    status: Optional[PermitStatus] = Field(default=None, description="Permit status")
    zip_code: Optional[str] = Field(default=None, description="5-digit ZIP code", min_length=5, max_length=5)
    days_back: Optional[int] = Field(default=90, ge=1, le=730, description="Days back from today to search")
    limit: Optional[int] = Field(default=DEFAULT_LIMIT, ge=1, le=MAX_LIMIT)
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v):
        if v and not v.startswith('19'):
            raise ValueError("Philadelphia ZIP codes start with '19'")
        return v


class AssessmentEquityInput(BaseModel):
    """Analyze assessment equity for a property."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra='forbid')
    
    address: Optional[str] = Field(default=None, description="Street address of subject property", max_length=200)
    parcel_number: Optional[str] = Field(default=None, description="Parcel number of subject property", min_length=5, max_length=20)
    zip_code: Optional[str] = Field(default=None, description="ZIP code for comparison area", min_length=5, max_length=5)
    category_code: Optional[CategoryCode] = Field(default=None, description="Property category for comparison")
    months_back: Optional[int] = Field(default=12, ge=3, le=36, description="Months of sales data to analyze")
    min_comparables: Optional[int] = Field(default=30, ge=10, le=200, description="Minimum comparables needed")
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)
    
    @field_validator('parcel_number')
    @classmethod
    def clean_parcel(cls, v):
        return v.replace('-', '').replace(' ', '') if v else None
    
    @field_validator('zip_code')
    @classmethod
    def validate_zip(cls, v):
        if v and not v.startswith('19'):
            raise ValueError("Philadelphia ZIP codes start with '19'")
        return v


# ==================== HELPER FUNCTIONS ====================

async def _make_api_request(query: str) -> Dict[str, Any]:
    """Make request to Philadelphia CARTO API."""
    await property_rate_limiter.wait_if_needed()
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            API_BASE_URL,
            params={"q": query, "format": "json"}
        )
        response.raise_for_status()
        return response.json()


async def _make_census_request(
    year: int,
    dataset: str,
    variables: List[str],
    geography: str,
    api_key: Optional[str] = None
) -> List[List[str]]:
    """Make request to Census API."""
    await census_rate_limiter.wait_if_needed()
    
    url = f"{CENSUS_API_BASE_URL}/{year}/{dataset}"
    params = {
        "get": ",".join(variables),
        "for": geography
    }
    if api_key:
        params["key"] = api_key
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


def _format_currency(value: Any) -> str:
    if value is None or value == '':
        return 'N/A'
    try:
        return f"${float(value):,.2f}"
    except (ValueError, TypeError):
        return str(value)


def _format_number(value: Any) -> str:
    if value is None or value == '':
        return 'N/A'
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


def _format_percent(value: float) -> str:
    return f"{value:.1f}%"


def _handle_api_error(e: Exception) -> str:
    """Enhanced error handling."""
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 429:
            return "⚠️ Rate limit exceeded. Please wait a moment and try again."
        elif e.response.status_code == 404:
            return "🔍 No data found. Please verify your search parameters."
        elif e.response.status_code == 400:
            return f"❌ Invalid request: {e.response.text}"
    return f"❌ Error: {str(e)}"


def _build_geography_string(
    state_fips: str,
    county_fips: Optional[str] = None,
    zip_code: Optional[str] = None
) -> str:
    """Build Census API geography string."""
    if zip_code:
        return f"zip code tabulation area:{zip_code}"
    elif county_fips:
        return f"county:{county_fips}&in=state:{state_fips}"
    else:
        return f"state:{state_fips}"


def _calculate_ratio_statistics(ratios: List[float]) -> Dict[str, float]:
    """
    Calculate assessment ratio statistics following IAAO standards.
    
    Returns: median, mean, COD, and sample size
    """
    if not ratios or len(ratios) < 3:
        return {
            "median_ratio": 0.0,
            "mean_ratio": 0.0,
            "cod": 0.0,
            "sample_size": len(ratios) if ratios else 0
        }
    
    # Sort ratios for median calculation
    sorted_ratios = sorted(ratios)
    n = len(sorted_ratios)
    
    # Median ratio
    if n % 2 == 0:
        median_ratio = (sorted_ratios[n//2 - 1] + sorted_ratios[n//2]) / 2
    else:
        median_ratio = sorted_ratios[n//2]
    
    # Mean ratio
    mean_ratio = sum(ratios) / n
    
    # COD = (Mean Absolute Deviation from Median / Median) * 100
    absolute_deviations = [abs(r - median_ratio) for r in ratios]
    mean_absolute_deviation = sum(absolute_deviations) / n
    cod = (mean_absolute_deviation / median_ratio * 100) if median_ratio > 0 else 0.0
    
    return {
        "median_ratio": round(median_ratio, 4),
        "mean_ratio": round(mean_ratio, 4),
        "cod": round(cod, 2),
        "sample_size": n
    }


def _calculate_prd(assessed_values: List[float], sale_prices: List[float]) -> float:
    """
    Calculate Price-Related Differential (PRD) following IAAO standards.
    
    PRD = Mean Ratio / Weighted Mean Ratio
    Values near 1.0 indicate no bias, >1.03 indicates regressivity, <0.98 indicates progressivity.
    """
    if not assessed_values or not sale_prices or len(assessed_values) != len(sale_prices):
        return 0.0
    
    # Calculate individual ratios
    ratios = []
    valid_pairs = []
    for av, sp in zip(assessed_values, sale_prices):
        if sp > 0:
            ratios.append(av / sp)
            valid_pairs.append((av, sp))
    
    if len(ratios) < 3:
        return 0.0
    
    # Mean ratio (unweighted)
    mean_ratio = sum(ratios) / len(ratios)
    
    # Weighted mean ratio = Sum(Assessments) / Sum(Sales)
    total_assessed = sum(av for av, sp in valid_pairs)
    total_sales = sum(sp for av, sp in valid_pairs)
    weighted_mean_ratio = total_assessed / total_sales if total_sales > 0 else 0.0
    
    # PRD
    prd = mean_ratio / weighted_mean_ratio if weighted_mean_ratio > 0 else 0.0
    
    return round(prd, 4)


def _calculate_prb(assessed_values: List[float], sale_prices: List[float]) -> float:
    """
    Calculate Price-Related Bias (PRB) using regression analysis.
    
    PRB is calculated from: ln(Assessed/Sales Median) = α + β * ln(Sale Price/Sales Median)
    Returns β coefficient. Values near 0 indicate no bias, negative indicates regressivity, positive indicates progressivity.
    """
    import math
    
    if not assessed_values or not sale_prices or len(assessed_values) != len(sale_prices):
        return 0.0
    
    # Filter valid pairs
    valid_pairs = [(av, sp) for av, sp in zip(assessed_values, sale_prices) if av > 0 and sp > 0]
    
    if len(valid_pairs) < 10:  # Need sufficient sample for regression
        return 0.0
    
    # Calculate median sale price
    sale_prices_only = [sp for av, sp in valid_pairs]
    sorted_sales = sorted(sale_prices_only)
    n = len(sorted_sales)
    median_sale = sorted_sales[n//2] if n % 2 == 1 else (sorted_sales[n//2-1] + sorted_sales[n//2]) / 2
    
    if median_sale <= 0:
        return 0.0
    
    # Calculate log-transformed variables
    try:
        x_values = [math.log(sp / median_sale) for av, sp in valid_pairs]
        y_values = [math.log((av/sp) / 1.0) for av, sp in valid_pairs]  # ln(ratio / median_ratio) where median_ratio ≈ 1
        
        # Simple linear regression: y = α + βx
        n = len(x_values)
        sum_x = sum(x_values)
        sum_y = sum(y_values)
        sum_xx = sum(x * x for x in x_values)
        sum_xy = sum(x * y for x, y in zip(x_values, y_values))
        
        # β = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
        denominator = n * sum_xx - sum_x * sum_x
        if denominator == 0:
            return 0.0
        
        beta = (n * sum_xy - sum_x * sum_y) / denominator
        
        return round(beta, 4)
    
    except (ValueError, ZeroDivisionError):
        return 0.0


def _interpret_ratio_stats(stats: Dict[str, Any], subject_ratio: Optional[float] = None) -> str:
    """Generate interpretation of ratio statistics following IAAO standards."""
    interpretation = []
    
    # Assessment Level
    median_asr = stats.get("median_ratio", 0) * 100
    if median_asr > 0:
        if 90 <= median_asr <= 110:
            interpretation.append(f"✓ Assessment level is acceptable ({median_asr:.1f}% of market value)")
        elif median_asr < 90:
            interpretation.append(f"⚠️ Properties are under-assessed ({median_asr:.1f}% of market value)")
        else:
            interpretation.append(f"⚠️ Properties are over-assessed ({median_asr:.1f}% of market value)")
    
    # COD - Uniformity
    cod = stats.get("cod", 0)
    if cod > 0:
        if cod <= 15:
            interpretation.append(f"✓ Good uniformity (COD: {cod:.1f}%)")
        elif cod <= 20:
            interpretation.append(f"⚠️ Acceptable uniformity (COD: {cod:.1f}%)")
        else:
            interpretation.append(f"❌ Poor uniformity (COD: {cod:.1f}%) - assessments are inconsistent")
    
    # PRD - Regressivity/Progressivity
    prd = stats.get("prd", 0)
    if prd > 0:
        if 0.98 <= prd <= 1.03:
            interpretation.append(f"✓ No price-related bias (PRD: {prd:.3f})")
        elif prd > 1.03:
            interpretation.append(f"❌ Regressive (PRD: {prd:.3f}) - lower-value properties over-assessed")
        else:
            interpretation.append(f"❌ Progressive (PRD: {prd:.3f}) - higher-value properties over-assessed")
    
    # PRB - Alternative bias measure
    prb = stats.get("prb", 0)
    if prb != 0:
        if abs(prb) <= 0.05:
            interpretation.append(f"✓ Minimal price bias (PRB: {prb:.3f})")
        elif prb < -0.05:
            interpretation.append(f"⚠️ Regressive bias detected (PRB: {prb:.3f})")
        elif prb > 0.05:
            interpretation.append(f"⚠️ Progressive bias detected (PRB: {prb:.3f})")
    
    # Subject property comparison
    if subject_ratio is not None:
        subject_asr = subject_ratio * 100
        median_asr = stats.get("median_ratio", 0) * 100
        if median_asr > 0:
            diff_pct = ((subject_asr - median_asr) / median_asr) * 100
            if abs(diff_pct) <= 10:
                interpretation.append(f"✓ Your property is assessed fairly ({subject_asr:.1f}% vs median {median_asr:.1f}%)")
            elif diff_pct > 10:
                interpretation.append(f"❌ Your property may be over-assessed ({subject_asr:.1f}% vs median {median_asr:.1f}%, +{diff_pct:.1f}%)")
            else:
                interpretation.append(f"⚠️ Your property is under-assessed ({subject_asr:.1f}% vs median {median_asr:.1f}%, {diff_pct:.1f}%)")
    
    return "\n".join(interpretation)


# ==================== METADATA-BASED FIELD DESCRIPTIONS ====================

PROPERTY_FIELD_DESCRIPTIONS = {
    'assessment_date': 'Date assessment was last changed',
    'basements': 'Basement type and finish',
    'building_code': 'Five-character building code',
    'category_code': 'Property category (1=Residential, 2=Hotels/Apts, 3=Store w/Dwelling, 4=Commercial, 5=Industrial, 6=Vacant)',
    'central_air': 'Has central air (Y/N)',
    'exterior_condition': 'Exterior condition rating',
    'fireplaces': 'Number of fireplaces',
    'garage_type': 'Type of garage',
    'number_of_bathrooms': 'Total bathrooms',
    'number_of_bedrooms': 'Total bedrooms',
    'number_of_rooms': 'Total rooms',
    'quality_grade': 'Building quality grade',
    'total_area': 'Total area in square feet',
    'total_livable_area': 'Total livable area in square feet',
    'year_built': 'Year property was built',
    'zoning': 'Zoning code',
    'fuel': 'Heating fuel type',
    'type_heater': 'Heater type',
    'view': 'View type from property',
    'topography': 'Land topography',
}


# ==================== TOOLS ====================

@mcp.tool(
    name="philly_search_assessments",
    annotations={
        "title": "Search Assessment History",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_search_assessments(params: AssessmentSearchInput) -> str:
    """
    Search property assessment history records.
    
    The assessments table contains historical market values and tax assessments by year.
    Fields: parcel_number, year, market_value, taxable_land, taxable_building, exempt_land, exempt_building
    """
    try:
        conditions = []
        
        if params.parcel_number:
            conditions.append(f"parcel_number = '{params.parcel_number}'")
        if params.year is not None:
            conditions.append(f"year = {params.year}")
        if params.min_market_value is not None:
            conditions.append(f"market_value >= {params.min_market_value}")
        if params.max_market_value is not None:
            conditions.append(f"market_value <= {params.max_market_value}")

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
        SELECT 
            parcel_number,
            year,
            market_value,
            taxable_land,
            taxable_building,
            exempt_land,
            exempt_building
        FROM assessments
        WHERE {where_clause}
        ORDER BY parcel_number, year DESC
        LIMIT {params.limit}
        OFFSET {params.offset}
        """

        result = await _make_api_request(query)

        if not result["rows"]:
            return "No assessment records found."

        records = result["rows"]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(records), "assessments": records}, indent=2)
        
        output = f"# Property Assessment Records\n\n**Results**: {len(records)}\n\n"

        current_parcel = None
        for record in records:
            parcel = record.get("parcel_number")
            if parcel != current_parcel:
                if current_parcel is not None:
                    output += "\n"
                output += f"## Parcel {parcel}\n\n"
                current_parcel = parcel

            output += f"### Year {record.get('year')}\n"
            output += f"- **Market Value**: {_format_currency(record.get('market_value'))}\n"
            output += f"- **Taxable Land**: {_format_currency(record.get('taxable_land'))}\n"
            output += f"- **Taxable Building**: {_format_currency(record.get('taxable_building'))}\n"
            output += f"- **Exempt Land**: {_format_currency(record.get('exempt_land'))}\n"
            output += f"- **Exempt Building**: {_format_currency(record.get('exempt_building'))}\n\n"

        if len(records) == params.limit:
            output += f"*Showing {params.limit} results. Use offset for pagination.*\n"

        return output

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="philly_search_properties",
    annotations={
        "title": "Search Properties",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_search_properties(params: PropertySearchInput) -> str:
    """
    Search properties by address, parcel number, or ZIP code.
    
    Basic search across the properties table which contains current property information.
    """
    try:
        conditions = []
        
        if params.address:
            conditions.append(f"location ILIKE '%{params.address.upper()}%'")
        if params.parcel_number:
            conditions.append(f"parcel_number = '{params.parcel_number}'")
        if params.zip_code:
            conditions.append(f"zip_code = '{params.zip_code}'")
        
        if not conditions:
            return "⚠️ Please provide at least one search criterion."
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
        SELECT 
            parcel_number,
            location,
            owner_1,
            owner_2,
            zip_code,
            market_value,
            sale_date,
            sale_price,
            number_of_bedrooms,
            number_of_bathrooms,
            total_area,
            year_built
        FROM opa_properties_public
        WHERE {where_clause}
        LIMIT {params.limit}
        """
        
        result = await _make_api_request(query)
        
        if not result["rows"]:
            return "No properties found."
        
        properties = result["rows"]
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(properties), "properties": properties}, indent=2)
        
        output = f"# Property Search Results\n\n**Found**: {len(properties)} propert{'y' if len(properties) == 1 else 'ies'}\n\n"
        
        for i, prop in enumerate(properties, 1):
            output += f"## {i}. {prop.get('location', 'N/A')}\n"
            output += f"- **Parcel**: {prop.get('parcel_number', 'N/A')}\n"
            output += f"- **Owner**: {prop.get('owner_1', 'N/A')}"
            if prop.get('owner_2'):
                output += f", {prop.get('owner_2')}"
            output += "\n"
            output += f"- **ZIP**: {prop.get('zip_code', 'N/A')}\n"
            output += f"- **Market Value**: {_format_currency(prop.get('market_value'))}\n"
            output += f"- **Beds/Baths**: {prop.get('number_of_bedrooms', 'N/A')}/{prop.get('number_of_bathrooms', 'N/A')}\n"
            output += f"- **Area**: {_format_number(prop.get('total_area'))} sq ft\n"
            output += f"- **Built**: {prop.get('year_built', 'N/A')}\n"
            if prop.get('sale_date'):
                output += f"- **Last Sale**: {prop.get('sale_date')} for {_format_currency(prop.get('sale_price'))}\n"
            output += "\n"
        
        if len(properties) == params.limit:
            output += f"*Showing first {params.limit} results.*\n"
        
        return output
    
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="philly_get_property_details",
    annotations={
        "title": "Get Complete Property Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_get_property_details(params: PropertyDetailsInput) -> str:
    """
    Get complete details for a specific property using all 72 available fields.
    
    Returns comprehensive information including ownership, physical characteristics,
    valuation, features, and more.
    """
    try:
        query = f"""
        SELECT *
        FROM opa_properties_public
        WHERE parcel_number = '{params.parcel_number}'
        LIMIT 1
        """
        
        result = await _make_api_request(query)
        
        if not result["rows"]:
            return f"❌ No property found: {params.parcel_number}"
        
        prop = result["rows"][0]
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"property": prop}, indent=2)
        
        output = f"# Property Details\n\n"
        output += f"## {prop.get('location', 'Address N/A')}\n\n"
        
        # Identification
        output += "### Identification\n"
        output += f"- **Parcel Number**: {prop.get('parcel_number', 'N/A')}\n"
        output += f"- **ZIP Code**: {prop.get('zip_code', 'N/A')}\n"
        output += f"- **Ward**: {prop.get('geographic_ward', 'N/A')}\n"
        output += f"- **Census Tract**: {prop.get('census_tract', 'N/A')}\n\n"
        
        # Ownership
        output += "### Ownership\n"
        output += f"- **Primary Owner**: {prop.get('owner_1', 'N/A')}\n"
        if prop.get('owner_2'):
            output += f"- **Secondary Owner**: {prop.get('owner_2')}\n"
        output += f"- **Mailing Address**: {prop.get('mailing_street', 'N/A')}\n"
        if prop.get('mailing_city_state'):
            output += f"- **Mailing City/State**: {prop.get('mailing_city_state')}\n"
        output += "\n"
        
        # Valuation
        output += "### Valuation\n"
        output += f"- **Market Value**: {_format_currency(prop.get('market_value'))}\n"
        output += f"- **Market Value Date**: {prop.get('market_value_date', 'N/A')}\n"
        output += f"- **Taxable Land**: {_format_currency(prop.get('taxable_land'))}\n"
        output += f"- **Taxable Building**: {_format_currency(prop.get('taxable_building'))}\n"
        if prop.get('exempt_land') or prop.get('exempt_building'):
            output += f"- **Exempt Land**: {_format_currency(prop.get('exempt_land'))}\n"
            output += f"- **Exempt Building**: {_format_currency(prop.get('exempt_building'))}\n"
        output += "\n"
        
        # Physical Characteristics
        output += "### Physical Characteristics\n"
        output += f"- **Year Built**: {prop.get('year_built', 'N/A')}"
        if prop.get('year_built_estimate') == 'Y':
            output += " (estimated)"
        output += "\n"
        output += f"- **Category**: {prop.get('category_code_description', prop.get('category_code', 'N/A'))}\n"
        output += f"- **Building Code**: {prop.get('building_code_description', prop.get('building_code', 'N/A'))}\n"
        output += f"- **Stories**: {prop.get('number_stories', 'N/A')}\n"
        output += f"- **Bedrooms**: {prop.get('number_of_bedrooms', 'N/A')}\n"
        output += f"- **Bathrooms**: {prop.get('number_of_bathrooms', 'N/A')}\n"
        output += f"- **Total Rooms**: {prop.get('number_of_rooms', 'N/A')}\n"
        output += f"- **Total Area**: {_format_number(prop.get('total_area'))} sq ft\n"
        output += f"- **Livable Area**: {_format_number(prop.get('total_livable_area'))} sq ft\n\n"
        
        # Quality & Condition
        output += "### Quality & Condition\n"
        output += f"- **Quality Grade**: {prop.get('quality_grade', 'N/A')}\n"
        output += f"- **Exterior Condition**: {prop.get('exterior_condition', 'N/A')}\n"
        if prop.get('interior_condition'):
            output += f"- **Interior Condition**: {prop.get('interior_condition')}\n"
        if prop.get('date_exterior_condition'):
            output += f"- **Condition Date**: {prop.get('date_exterior_condition')}\n"
        output += "\n"
        
        # Features & Systems
        output += "### Features & Systems\n"
        output += f"- **Basement**: {prop.get('basements', 'N/A')}\n"
        output += f"- **Garage**: {prop.get('garage_type', 'N/A')}"
        if prop.get('garage_spaces'):
            output += f" ({prop.get('garage_spaces')} spaces)"
        output += "\n"
        output += f"- **Central Air**: {prop.get('central_air', 'N/A')}\n"
        output += f"- **Heater Type**: {prop.get('type_heater', 'N/A')}\n"
        output += f"- **Fuel**: {prop.get('fuel', 'N/A')}\n"
        if prop.get('fireplaces') and prop.get('fireplaces') != '0':
            output += f"- **Fireplaces**: {prop.get('fireplaces')}\n"
        output += "\n"
        
        # Lot Information
        output += "### Lot Information\n"
        output += f"- **Frontage**: {prop.get('frontage', 'N/A')} ft\n"
        output += f"- **Depth**: {prop.get('depth', 'N/A')} ft\n"
        output += f"- **Shape**: {prop.get('shape', 'N/A')}\n"
        output += f"- **Topography**: {prop.get('topography', 'N/A')}\n"
        if prop.get('view') and prop.get('view') not in ['I', '0']:
            output += f"- **View**: {prop.get('view')}\n"
        output += "\n"
        
        # Sales History
        if prop.get('sale_date'):
            output += "### Sales History\n"
            output += f"- **Last Sale Date**: {prop.get('sale_date')}\n"
            output += f"- **Sale Price**: {_format_currency(prop.get('sale_price'))}\n"
            if prop.get('recording_date'):
                output += f"- **Recording Date**: {prop.get('recording_date')}\n"
            output += "\n"
        
        # Zoning
        if prop.get('zoning'):
            output += "### Zoning\n"
            output += f"- **Zoning Code**: {prop.get('zoning')}\n\n"
        
        output += "*Data from Philadelphia Office of Property Assessment*\n"
        
        return output
    
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="philly_search_by_characteristics",
    annotations={
        "title": "Advanced Property Search",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_search_by_characteristics(params: PropertyCharacteristicsInput) -> str:
    """
    Search properties by detailed characteristics including bedrooms, bathrooms,
    quality grade, condition, features, and more.
    
    Supports filtering by: bedrooms, bathrooms, area, year built, quality grade,
    exterior condition, basement type, garage type, central air, fireplaces, and value.
    """
    try:
        conditions = []
        
        # Basic filters
        if params.zip_code:
            conditions.append(f"zip_code = '{params.zip_code}'")
        if params.category_code:
            conditions.append(f"category_code = '{params.category_code.value}'")
        
        # Physical characteristics
        if params.min_bedrooms is not None:
            conditions.append(f"number_of_bedrooms >= {params.min_bedrooms}")
        if params.max_bedrooms is not None:
            conditions.append(f"number_of_bedrooms <= {params.max_bedrooms}")
        if params.min_bathrooms is not None:
            conditions.append(f"number_of_bathrooms >= {params.min_bathrooms}")
        if params.max_bathrooms is not None:
            conditions.append(f"number_of_bathrooms <= {params.max_bathrooms}")
        if params.min_total_area is not None:
            conditions.append(f"total_area >= {params.min_total_area}")
        if params.max_total_area is not None:
            conditions.append(f"total_area <= {params.max_total_area}")
        if params.min_year_built is not None:
            conditions.append(f"year_built >= {params.min_year_built}")
        if params.max_year_built is not None:
            conditions.append(f"year_built <= {params.max_year_built}")
        
        # Quality and condition
        if params.quality_grade:
            conditions.append(f"quality_grade = '{params.quality_grade.value}'")
        if params.exterior_condition:
            conditions.append(f"exterior_condition = '{params.exterior_condition.value}'")
        
        # Features
        if params.basement_type:
            conditions.append(f"basements = '{params.basement_type.value}'")
        if params.garage_type:
            conditions.append(f"garage_type = '{params.garage_type.value}'")
        if params.central_air:
            conditions.append(f"central_air = '{params.central_air}'")
        if params.fireplaces is not None:
            conditions.append(f"fireplaces >= {params.fireplaces}")
        
        # Value
        if params.min_market_value is not None:
            conditions.append(f"market_value >= {params.min_market_value}")
        if params.max_market_value is not None:
            conditions.append(f"market_value <= {params.max_market_value}")
        
        if not conditions:
            return "⚠️ Please provide at least one search criterion."
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
        SELECT 
            parcel_number,
            location,
            zip_code,
            market_value,
            number_of_bedrooms,
            number_of_bathrooms,
            year_built,
            total_area,
            quality_grade,
            exterior_condition,
            basements,
            garage_type,
            central_air,
            fireplaces
        FROM opa_properties_public
        WHERE {where_clause}
        ORDER BY market_value DESC
        LIMIT {params.limit}
        """
        
        result = await _make_api_request(query)
        
        if not result["rows"]:
            return "No properties found matching these criteria."
        
        properties = result["rows"]
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(properties), "properties": properties}, indent=2)
        
        output = f"# Advanced Property Search Results\n\n"
        output += f"**Found**: {len(properties)} propert{'y' if len(properties) == 1 else 'ies'}\n\n"
        
        for i, prop in enumerate(properties, 1):
            output += f"## {i}. {prop.get('location', 'N/A')}\n"
            output += f"- **Parcel**: {prop.get('parcel_number', 'N/A')}\n"
            output += f"- **Market Value**: {_format_currency(prop.get('market_value'))}\n"
            output += f"- **Beds/Baths**: {prop.get('number_of_bedrooms', 'N/A')}/{prop.get('number_of_bathrooms', 'N/A')}\n"
            output += f"- **Year Built**: {prop.get('year_built', 'N/A')} | **Area**: {_format_number(prop.get('total_area'))} sq ft\n"
            output += f"- **Quality**: {prop.get('quality_grade', 'N/A')} | **Condition**: {prop.get('exterior_condition', 'N/A')}\n"
            
            features = []
            if prop.get('central_air') == 'Y':
                features.append("Central Air")
            if prop.get('basements') and prop.get('basements') != '0':
                features.append(f"Basement ({prop.get('basements')})")
            if prop.get('garage_type') and prop.get('garage_type') != '0':
                features.append("Garage")
            if prop.get('fireplaces') and prop.get('fireplaces') not in ['0', None]:
                features.append(f"{prop.get('fireplaces')} Fireplace(s)")
            
            if features:
                output += f"- **Features**: {', '.join(features)}\n"
            output += "\n"
        
        if len(properties) == params.limit:
            output += f"*Showing top {params.limit} results by value.*\n"
        
        return output
    
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="philly_search_recent_sales",
    annotations={
        "title": "Search Recent Property Sales",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_search_recent_sales(params: PropertySalesInput) -> str:
    """
    Find properties with recent sales/transfers.
    
    Useful for market analysis and investment research. Can filter by ZIP code,
    sale price range, and time period.
    """
    try:
        conditions = ["sale_date IS NOT NULL", "sale_price > 0"]
        
        # Calculate date threshold
        from datetime import datetime, timedelta
        threshold_date = datetime.now() - timedelta(days=params.months_back * 30)
        date_str = threshold_date.strftime('%Y-%m-%d')
        conditions.append(f"sale_date >= '{date_str}'")
        
        if params.zip_code:
            conditions.append(f"zip_code = '{params.zip_code}'")
        if params.min_sale_price is not None:
            conditions.append(f"sale_price >= {params.min_sale_price}")
        if params.max_sale_price is not None:
            conditions.append(f"sale_price <= {params.max_sale_price}")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
        SELECT 
            parcel_number,
            location,
            zip_code,
            sale_date,
            sale_price,
            market_value,
            number_of_bedrooms,
            number_of_bathrooms,
            total_area,
            year_built
        FROM opa_properties_public
        WHERE {where_clause}
        ORDER BY sale_date DESC
        LIMIT {params.limit}
        """
        
        result = await _make_api_request(query)
        
        if not result["rows"]:
            return f"No recent sales found in the last {params.months_back} months."
        
        sales = result["rows"]
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(sales), "sales": sales}, indent=2)
        
        output = f"# Recent Property Sales\n\n"
        output += f"**Period**: Last {params.months_back} months\n"
        output += f"**Found**: {len(sales)} sale(s)\n\n"
        
        for i, prop in enumerate(sales, 1):
            output += f"## {i}. {prop.get('location', 'N/A')}\n"
            output += f"- **Parcel**: {prop.get('parcel_number', 'N/A')}\n"
            output += f"- **Sale Date**: {prop.get('sale_date', 'N/A')}\n"
            output += f"- **Sale Price**: {_format_currency(prop.get('sale_price'))}\n"
            output += f"- **Current Market Value**: {_format_currency(prop.get('market_value'))}\n"
            output += f"- **Beds/Baths**: {prop.get('number_of_bedrooms', 'N/A')}/{prop.get('number_of_bathrooms', 'N/A')}\n"
            output += f"- **Area**: {_format_number(prop.get('total_area'))} sq ft | **Built**: {prop.get('year_built', 'N/A')}\n\n"
        
        return output
    
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="census_get_demographics",
    annotations={
        "title": "Get Census Demographics",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def census_get_demographics(params: CensusDemographicsInput) -> str:
    """
    Retrieve demographic data from US Census Bureau.
    
    Includes population, age, race/ethnicity, households, and income data.
    API key loaded from environment if not provided.
    """
    try:
        variables = [
            "NAME",
            "B01001_001E",  # Total population
            "B01002_001E",  # Median age
            "B02001_002E",  # White alone
            "B02001_003E",  # Black/African American
            "B02001_005E",  # Asian alone
            "B03003_003E",  # Hispanic/Latino
            "B11001_001E",  # Total households
            "B19013_001E",  # Median household income
        ]

        geography = _build_geography_string(
            params.state_fips,
            params.county_fips,
            params.zip_code
        )

        data = await _make_census_request(
            params.year,
            params.dataset.value,
            variables,
            geography,
            params.api_key
        )

        if len(data) < 2:
            return "No demographic data found."

        headers = data[0]
        row = data[1]
        result = dict(zip(headers, row))

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"demographics": result}, indent=2)
        
        output = f"# Census Demographics: {result.get('NAME', 'Unknown')}\n\n"
        output += f"**Year**: {params.year} | **Dataset**: {params.dataset.value}\n\n"

        output += "## Population\n"
        total_pop = int(result.get('B01001_001E', 0))
        output += f"- **Total Population**: {_format_number(total_pop)}\n"
        output += f"- **Median Age**: {result.get('B01002_001E', 'N/A')} years\n\n"

        output += "## Race & Ethnicity\n"
        white = int(result.get('B02001_002E', 0))
        black = int(result.get('B02001_003E', 0))
        asian = int(result.get('B02001_005E', 0))
        hispanic = int(result.get('B03003_003E', 0))

        if total_pop > 0:
            output += f"- **White**: {_format_number(white)} ({_format_percent(white/total_pop*100)})\n"
            output += f"- **Black/African American**: {_format_number(black)} ({_format_percent(black/total_pop*100)})\n"
            output += f"- **Asian**: {_format_number(asian)} ({_format_percent(asian/total_pop*100)})\n"
            output += f"- **Hispanic/Latino**: {_format_number(hispanic)} ({_format_percent(hispanic/total_pop*100)})\n\n"

        output += "## Households & Income\n"
        output += f"- **Total Households**: {_format_number(result.get('B11001_001E'))}\n"
        output += f"- **Median Household Income**: {_format_currency(result.get('B19013_001E'))}\n\n"

        output += "*Source: US Census Bureau*\n"

        return output

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return "Census data not found. Verify FIPS codes (PA=42, Philadelphia=101)."
        elif e.response.status_code == 400:
            return "Invalid request. Check FIPS codes and parameters."
        else:
            return _handle_api_error(e)
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="philly_search_permits",
    annotations={
        "title": "Search Building Permits",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_search_permits(params: PermitSearchInput) -> str:
    """
    Search Philadelphia building permits.
    
    Find permits by address, permit number, OPA account, type, or status.
    Useful for tracking construction activity, compliance research, and development analysis.
    """
    try:
        conditions = []
        
        # Calculate date threshold
        from datetime import datetime, timedelta
        threshold_date = datetime.now() - timedelta(days=params.days_back)
        date_str = threshold_date.strftime('%Y-%m-%d')
        conditions.append(f"permitissuedate >= '{date_str}'")
        
        if params.address:
            conditions.append(f"address ILIKE '%{params.address}%'")
        if params.permit_number:
            conditions.append(f"permitnumber = '{params.permit_number}'")
        if params.opa_account_num:
            conditions.append(f"opa_account_num = '{params.opa_account_num}'")
        if params.permit_type:
            conditions.append(f"permittype ILIKE '%{params.permit_type}%'")
        if params.status:
            conditions.append(f"status = '{params.status.value}'")
        if params.zip_code:
            conditions.append(f"zip LIKE '{params.zip_code}%'")
        
        where_clause = " AND ".join(conditions)
        
        query = f"""
        SELECT 
            permitnumber,
            address,
            zip,
            permittype,
            permitdescription,
            status,
            permitissuedate,
            permitcompleteddate,
            typeofwork,
            approvedscopeofwork,
            opa_account_num,
            opa_owner,
            contractorname,
            commercialorresidential,
            systemofrecord
        FROM permits
        WHERE {where_clause}
        ORDER BY permitissuedate DESC
        LIMIT {params.limit}
        """
        
        result = await _make_api_request(query)
        
        if not result["rows"]:
            return f"No permits found in the last {params.days_back} days with the specified criteria."
        
        permits = result["rows"]
        
        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(permits), "permits": permits}, indent=2)
        
        output = f"# Philadelphia Building Permits\n\n"
        output += f"**Period**: Last {params.days_back} days\n"
        output += f"**Found**: {len(permits)} permit(s)\n\n"
        
        for i, permit in enumerate(permits, 1):
            output += f"## {i}. {permit.get('address', 'N/A')}\n"
            output += f"- **Permit Number**: {permit.get('permitnumber', 'N/A')}\n"
            output += f"- **Type**: {permit.get('permittype', 'N/A')} - {permit.get('permitdescription', 'N/A')}\n"
            output += f"- **Status**: {permit.get('status', 'N/A')}\n"
            output += f"- **Issue Date**: {permit.get('permitissuedate', 'N/A')}\n"
            
            if permit.get('permitcompleteddate'):
                output += f"- **Completed**: {permit.get('permitcompleteddate')}\n"
            
            if permit.get('typeofwork'):
                output += f"- **Type of Work**: {permit.get('typeofwork')}\n"
            
            if permit.get('approvedscopeofwork'):
                scope = permit.get('approvedscopeofwork', '')
                if len(scope) > 100:
                    scope = scope[:97] + "..."
                output += f"- **Scope**: {scope}\n"
            
            if permit.get('opa_account_num'):
                output += f"- **OPA Account**: {permit.get('opa_account_num')}\n"
            
            if permit.get('opa_owner'):
                output += f"- **Owner**: {permit.get('opa_owner')}\n"
            
            if permit.get('contractorname'):
                output += f"- **Contractor**: {permit.get('contractorname')}\n"
            
            if permit.get('commercialorresidential'):
                output += f"- **Property Type**: {permit.get('commercialorresidential')}\n"
            
            output += f"- **ZIP**: {permit.get('zip', 'N/A')}\n"
            output += f"- **System**: {permit.get('systemofrecord', 'N/A')}\n"
            output += "\n"
        
        if len(permits) == params.limit:
            output += f"*Showing first {params.limit} results. Use limit parameter for more.*\n"
        
        return output
    
    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="philly_analyze_assessment_equity",
    annotations={
        "title": "Analyze Assessment Equity",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
    }
)
async def philly_analyze_assessment_equity(params: AssessmentEquityInput) -> str:
    """
    Analyze assessment equity for a property using IAAO standards.
    
    Calculates Assessment-to-Sales Ratio (ASR), Coefficient of Dispersion (COD),
    Price-Related Differential (PRD), and Price-Related Bias (PRB) for comparison area.
    
    Useful for citizens evaluating whether their property assessment is fair and
    whether they have grounds for an appeal.
    """
    try:
        from datetime import datetime, timedelta
        
        # Step 1: Get subject property if specified
        subject_property = None
        subject_ratio = None
        
        if params.address or params.parcel_number:
            subject_conditions = []
            if params.address:
                subject_conditions.append(f"location ILIKE '%{params.address}%'")
            if params.parcel_number:
                subject_conditions.append(f"parcel_number = '{params.parcel_number}'")
            
            subject_query = f"""
            SELECT 
                parcel_number,
                location,
                zip_code,
                market_value,
                sale_price,
                sale_date,
                category_code,
                number_of_bedrooms,
                number_of_bathrooms,
                total_area
            FROM opa_properties_public
            WHERE {' AND '.join(subject_conditions)}
            LIMIT 1
            """
            
            subject_result = await _make_api_request(subject_query)
            
            if subject_result["rows"]:
                subject_property = subject_result["rows"][0]
                # Calculate subject ratio if they have recent sale
                if subject_property.get('sale_price') and float(subject_property.get('sale_price', 0)) > 0:
                    subject_ratio = float(subject_property.get('market_value', 0)) / float(subject_property.get('sale_price'))
            else:
                return f"Subject property not found. Please verify address or parcel number."
        
        # Step 2: Build comparison query
        threshold_date = datetime.now() - timedelta(days=params.months_back * 30)
        date_str = threshold_date.strftime('%Y-%m-%d')
        
        comp_conditions = [
            "sale_date IS NOT NULL",
            "sale_price > 0",
            "market_value > 0",
            f"sale_date >= '{date_str}'"
        ]
        
        # Use subject property characteristics for comparison if available
        if subject_property:
            if not params.zip_code and subject_property.get('zip_code'):
                comp_conditions.append(f"zip_code = '{subject_property.get('zip_code')}'")
            if not params.category_code and subject_property.get('category_code'):
                comp_conditions.append(f"category_code = '{subject_property.get('category_code')}'")
        
        # Override with user-specified filters
        if params.zip_code:
            comp_conditions.append(f"zip_code = '{params.zip_code}'")
        if params.category_code:
            comp_conditions.append(f"category_code = '{params.category_code.value}'")
        
        where_clause = " AND ".join(comp_conditions)
        
        comp_query = f"""
        SELECT 
            parcel_number,
            location,
            market_value,
            sale_price,
            sale_date
        FROM opa_properties_public
        WHERE {where_clause}
        ORDER BY sale_date DESC
        LIMIT 500
        """
        
        result = await _make_api_request(comp_query)
        
        if not result["rows"] or len(result["rows"]) < params.min_comparables:
            return f"Insufficient sales data. Found {len(result['rows']) if result['rows'] else 0} sales, need at least {params.min_comparables}."
        
        comparables = result["rows"]
        
        # Step 3: Calculate statistics
        assessed_values = []
        sale_prices = []
        ratios = []
        
        for comp in comparables:
            mv = float(comp.get('market_value', 0))
            sp = float(comp.get('sale_price', 0))
            if mv > 0 and sp > 0:
                assessed_values.append(mv)
                sale_prices.append(sp)
                ratios.append(mv / sp)
        
        if len(ratios) < params.min_comparables:
            return f"Insufficient valid sales data. Found {len(ratios)} valid sales, need at least {params.min_comparables}."
        
        # Calculate all statistics
        ratio_stats = _calculate_ratio_statistics(ratios)
        prd = _calculate_prd(assessed_values, sale_prices)
        prb = _calculate_prb(assessed_values, sale_prices)
        
        ratio_stats['prd'] = prd
        ratio_stats['prb'] = prb
        
        # Step 4: Format output
        if params.response_format == ResponseFormat.JSON:
            output = {
                "subject_property": subject_property,
                "subject_ratio": subject_ratio,
                "comparison_area": {
                    "zip_code": params.zip_code or (subject_property.get('zip_code') if subject_property else None),
                    "category_code": params.category_code.value if params.category_code else (subject_property.get('category_code') if subject_property else None),
                    "months_analyzed": params.months_back,
                    "sample_size": len(ratios)
                },
                "statistics": ratio_stats,
                "interpretation": _interpret_ratio_stats(ratio_stats, subject_ratio).split('\n')
            }
            return json.dumps(output, indent=2)
        
        # Markdown output
        output = "# Assessment Equity Analysis\n\n"
        
        if subject_property:
            output += "## Subject Property\n"
            output += f"- **Address**: {subject_property.get('location', 'N/A')}\n"
            output += f"- **Parcel**: {subject_property.get('parcel_number', 'N/A')}\n"
            output += f"- **Market Value**: {_format_currency(subject_property.get('market_value'))}\n"
            if subject_property.get('sale_price') and float(subject_property.get('sale_price', 0)) > 0:
                output += f"- **Last Sale**: {_format_currency(subject_property.get('sale_price'))} on {subject_property.get('sale_date', 'N/A')}\n"
                if subject_ratio:
                    output += f"- **Assessment Ratio**: {subject_ratio*100:.1f}%\n"
            output += "\n"
        
        output += "## Comparison Area\n"
        comp_zip = params.zip_code or (subject_property.get('zip_code') if subject_property else 'Various')
        comp_cat = params.category_code.value if params.category_code else (subject_property.get('category_code') if subject_property else 'All')
        output += f"- **ZIP Code**: {comp_zip}\n"
        output += f"- **Property Category**: {comp_cat}\n"
        output += f"- **Time Period**: Last {params.months_back} months\n"
        output += f"- **Sample Size**: {len(ratios)} sales\n\n"
        
        output += "## Statistical Analysis (IAAO Standards)\n\n"
        
        output += "### Assessment Level\n"
        median_asr = ratio_stats['median_ratio'] * 100
        mean_asr = ratio_stats['mean_ratio'] * 100
        output += f"- **Median ASR**: {median_asr:.1f}% (properties assessed at {median_asr:.1f}% of sale price)\n"
        output += f"- **Mean ASR**: {mean_asr:.1f}%\n"
        output += f"- **IAAO Standard**: 90-110%\n\n"
        
        output += "### Uniformity (COD)\n"
        output += f"- **COD**: {ratio_stats['cod']:.1f}%\n"
        output += f"- **IAAO Standard**: ≤15% for residential\n"
        output += f"- **Interpretation**: {'Acceptable' if ratio_stats['cod'] <= 15 else 'Poor'} uniformity\n\n"
        
        output += "### Vertical Equity (PRD & PRB)\n"
        output += f"- **PRD**: {prd:.3f}\n"
        output += f"- **IAAO Standard**: 0.98-1.03\n"
        output += f"- **PRB**: {prb:.3f}\n"
        output += f"- **IAAO Standard**: -0.05 to +0.05\n\n"
        
        output += "## Interpretation\n"
        output += _interpret_ratio_stats(ratio_stats, subject_ratio) + "\n\n"
        
        output += "---\n"
        output += "*Analysis based on IAAO Standard on Ratio Studies*\n"
        output += f"*Data: {len(ratios)} arms-length sales in last {params.months_back} months*\n"
        
        return output
    
    except Exception as e:
        return _handle_api_error(e)


# ==================== MAIN ====================

if __name__ == "__main__":
    import sys
    
    print("=" * 70, file=sys.stderr)
    print("Philadelphia Property & Census MCP Server - METADATA-DRIVEN", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print(f"[OK] Properties table: 72 fields", file=sys.stderr)
    print(f"[OK] Assessments table: 7 fields", file=sys.stderr)
    print(f"[OK] Permits table: 44 fields", file=sys.stderr)
    
    if DEFAULT_CENSUS_API_KEY:
        print("[OK] Census API key loaded", file=sys.stderr)
    else:
        print("[WARNING] No Census API key (limited rate)", file=sys.stderr)
    
    print(f"[OK] Default Census year: {DEFAULT_CENSUS_YEAR}", file=sys.stderr)
    print(f"[OK] Default dataset: {DEFAULT_CENSUS_DATASET}", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    print("Starting MCP server...", file=sys.stderr)
    print("=" * 70, file=sys.stderr)
    
    mcp.run(transport="stdio")