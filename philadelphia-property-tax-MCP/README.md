# Philadelphia Property & Census MCP Server with Claude API Integration

Complete setup for running your MCP server with Claude API and a local chatbot interface.

## 📋 What You Get

1. **Backend API Server** (`backend_server.py`) - Connects your MCP server to Claude API
2. **Web Chatbot Interface** (`chatbot_interface.html`) - Beautiful UI to interact with Claude
3. **Your Existing MCP Server** - Philadelphia property and census data tools

## 🚀 Setup Instructions

### Step 1: Install Dependencies

Using your Anaconda environment:

```bash
# Activate your conda environment
conda activate your_env_name

# Install required packages
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

1. Copy the template:
   ```bash
   cp .env.template .env
   ```

2. Edit `.env` and add your API keys:
   ```
   ANTHROPIC_API_KEY=sk-ant-xxxxx  # Get from console.anthropic.com
   MCP_SERVER_PATH=./philadelphia_property_census_mcp.py
   PYTHON_PATH=/path/to/your/anaconda/python  # or just 'python'
   CENSUS_API_KEY=your_census_key  # Optional
   ```

### Step 3: Start the Backend Server

```bash
python backend_server.py
```

You should see:
```
MCP-Claude API Backend Server
============================================================
MCP Server Path: ./philadelphia_property_census_mcp.py
Python Path: python
Starting Flask server on http://localhost:5000
============================================================
```

### Step 4: Open the Chatbot Interface

Simply open `chatbot_interface.html` in your web browser. It will automatically connect to the backend at `localhost:5000`.

## 💡 Usage Examples

Try asking:
- "Find properties in zip code 19103 with market value over $500,000"
- "What are the demographics for Philadelphia County?"
- "Show me recent property sales in Center City"
- "Compare median household income between Philadelphia and surrounding counties"

## 🏗️ Architecture

```
User Browser (chatbot_interface.html)
    ↓ HTTP POST
Backend Server (backend_server.py)
    ↓ Uses Anthropic SDK
Claude API
    ↓ Tool calls
MCP Server (philadelphia_property_census_mcp.py)
    ↓ API calls
Philadelphia CARTO API / Census API
```

## 🔧 Suggested MCP Server Improvements

Based on your current code, here are recommendations:

### 1. **Add Missing Tool Implementations**

Your code has comments about omitted tools. Add these back:

```python
@mcp.tool(name="philly_search_properties")
async def philly_search_properties(params: PropertySearchInput) -> str:
    """Search properties by address, parcel number, or ZIP code."""
    # Implementation needed
    pass

@mcp.tool(name="philly_get_property_details")
async def philly_get_property_details(params: PropertyDetailsInput) -> str:
    """Get complete details for a specific property."""
    # Implementation needed
    pass

@mcp.tool(name="philly_search_by_characteristics")
async def philly_search_by_characteristics(params: PropertyCharacteristicsInput) -> str:
    """Search properties by physical characteristics."""
    # Implementation needed
    pass

@mcp.tool(name="census_get_economic_data")
async def census_get_economic_data(params: CensusEconomicInput) -> str:
    """Get economic data from Census."""
    # Implementation needed
    pass

@mcp.tool(name="census_get_housing_data")
async def census_get_housing_data(params: CensusHousingInput) -> str:
    """Get housing data from Census."""
    # Implementation needed
    pass
```

### 2. **Add Caching for Better Performance**

```python
from functools import lru_cache
import time

# Add caching to frequently accessed data
@lru_cache(maxsize=100)
def _cached_api_request(query: str, cache_key: str):
    """Cache API requests for 5 minutes."""
    return _make_api_request(query)
```

### 3. **Add Rate Limiting and Error Handling**

```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.calls = []
    
    async def wait_if_needed(self):
        now = datetime.now()
        # Remove calls older than 1 minute
        self.calls = [call for call in self.calls 
                     if now - call < timedelta(minutes=1)]
        
        if len(self.calls) >= self.calls_per_minute:
            sleep_time = 60 - (now - self.calls[0]).seconds
            await asyncio.sleep(sleep_time)
        
        self.calls.append(now)

rate_limiter = RateLimiter(calls_per_minute=60)

async def _make_api_request(query: str):
    await rate_limiter.wait_if_needed()
    # ... existing code
```

### 4. **Add Aggregation and Analysis Tools**

```python
@mcp.tool(name="philly_analyze_market_trends")
async def philly_analyze_market_trends(params: MarketTrendsInput) -> str:
    """
    Analyze property market trends over time.
    Shows average values, price changes, and market statistics.
    """
    # Aggregate data by year and calculate trends
    pass

@mcp.tool(name="philly_compare_neighborhoods")
async def philly_compare_neighborhoods(params: NeighborhoodCompareInput) -> str:
    """
    Compare multiple ZIP codes or neighborhoods.
    Shows side-by-side comparison of key metrics.
    """
    pass
```

### 5. **Add Geospatial Search**

```python
class GeoSearchInput(BaseModel):
    latitude: float = Field(..., description="Center latitude")
    longitude: float = Field(..., description="Center longitude")
    radius_miles: float = Field(..., description="Search radius in miles")
    
@mcp.tool(name="philly_search_by_location")
async def philly_search_by_location(params: GeoSearchInput) -> str:
    """Search properties within a radius of a lat/lon point."""
    # Use PostGIS functions in CARTO
    pass
```

### 6. **Add Data Export**

```python
@mcp.tool(name="philly_export_to_csv")
async def philly_export_to_csv(params: ExportInput) -> str:
    """Export search results to CSV format."""
    import csv
    from io import StringIO
    # Export data as downloadable CSV
    pass
```

### 7. **Improve Error Messages**

```python
def _handle_api_error(e: Exception) -> str:
    """Enhanced error handling with specific guidance."""
    if isinstance(e, httpx.HTTPStatusError):
        if e.response.status_code == 429:
            return (
                "⚠️ Rate limit exceeded. Please wait a moment and try again.\n"
                "Consider adding rate limiting to your requests."
            )
        elif e.response.status_code == 404:
            return (
                "🔍 No data found. Please check:\n"
                "- Parcel numbers are formatted correctly\n"
                "- Years are valid (1900-2030)\n"
                "- Geographic codes (FIPS, ZIP) are correct"
            )
    return f"❌ Error: {str(e)}"
```

### 8. **Add Input Validation Helpers**

```python
@field_validator('zip_code')
@classmethod
def validate_zip_code(cls, v: Optional[str]) -> Optional[str]:
    """Validate Philadelphia ZIP codes."""
    if v is None:
        return None
    if not v.startswith('19'):
        raise ValueError("Philadelphia ZIP codes start with '19'")
    return v

@field_validator('state_fips')
@classmethod
def validate_state_fips(cls, v: Optional[str]) -> Optional[str]:
    """Provide friendly state FIPS validation."""
    if v is None:
        return None
    # Pennsylvania = 42
    if v not in VALID_STATE_FIPS:
        raise ValueError(
            f"Invalid state FIPS code. "
            f"Use '42' for Pennsylvania. "
            f"See: https://www.census.gov/library/reference/code-lists/ansi.html"
        )
    return v
```

### 9. **Add Batch Operations**

```python
@mcp.tool(name="philly_batch_property_lookup")
async def philly_batch_property_lookup(params: BatchLookupInput) -> str:
    """Look up multiple properties at once."""
    results = []
    for parcel in params.parcel_numbers:
        result = await philly_get_property_details(
            PropertyDetailsInput(parcel_number=parcel)
        )
        results.append(result)
    return "\n\n".join(results)
```

### 10. **Add Recent Sales Tracking**

```python
@mcp.tool(name="philly_search_recent_sales")
async def philly_search_recent_sales(params: RecentSalesInput) -> str:
    """
    Find properties with recent sales/transfers.
    Useful for market analysis and investment research.
    """
    query = """
    SELECT *
    FROM properties
    WHERE sale_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 6 MONTH)
    ORDER BY sale_date DESC
    """
    # Implementation
    pass
```

## 🐛 Troubleshooting

### Backend won't start
- Check that all dependencies are installed: `pip list | grep -E "(flask|anthropic|mcp)"`
- Verify `.env` file has correct API key
- Make sure port 5000 is not in use

### Chatbot shows connection error
- Ensure backend is running on port 5000
- Check browser console for CORS errors
- Try accessing http://localhost:5000/health directly

### MCP tools not working
- Verify MCP_SERVER_PATH points to your actual file
- Check that PYTHON_PATH is correct (test: `which python` or `where python`)
- Look at backend console for MCP connection errors

### Census API errors
- Get a free key from: https://api.census.gov/data/key_signup.html
- Add it to your `.env` file
- Some census endpoints have different rate limits

## 📚 API Documentation

### Backend Endpoints

**POST /chat**
```json
{
  "message": "Find properties in 19103",
  "conversation_history": []
}
```

**GET /tools**
- Returns list of available MCP tools

**GET /health**
- Health check endpoint

## 🛡️ Design Decisions & Privacy Considerations

This tool displays owner names when looking up a property by address, consistent with Philadelphia's public records. However, reverse owner lookup (searching all properties by owner name) has been intentionally disabled. The goal is property-level transparency, not owner-level surveillance. AI tools significantly reduce the friction of aggregating public records, and this project errs on the side of the city's apparent intent rather than the maximum technically permissible access.

## 🔐 Security Notes

- Never commit your `.env` file
- Keep API keys secure
- For production, add authentication
- Consider rate limiting on the backend

## 📖 Resources

- [Anthropic API Docs](https://docs.anthropic.com)
- [MCP Documentation](https://modelcontextprotocol.io)
- [Philadelphia Open Data](https://www.opendataphilly.org)
- [Census API Guide](https://www.census.gov/data/developers/guidance/api-user-guide.html)

## 🤝 Contributing

Feel free to add more tools, improve the UI, or enhance error handling!
