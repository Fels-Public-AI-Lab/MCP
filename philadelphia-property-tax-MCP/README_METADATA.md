# Philadelphia Property & Census MCP Server - Complete Package

## 📦 What's Included

This package contains everything you need to run your Philadelphia property and census data MCP server with Claude API and a local chatbot interface.

### Files:

1. **philadelphia_property_census_mcp_metadata_driven.py** - ⭐ **RECOMMENDED VERSION**
   - Built from actual CARTO API metadata
   - 72 accurate property fields
   - 7 assessment history fields
   - Proper enums and validation
   - Complete field descriptions

2. **backend_server.py** - Flask API server
   - Connects MCP to Claude API
   - Handles tool calls
   - REST endpoints for chatbot

3. **chatbot_interface.html** - Web UI
   - Beautiful chatbot interface
   - Real-time responses
   - Token usage tracking

4. **requirements.txt** - All dependencies

5. **. env.template** - Configuration template

## 🎯 Major Improvements from Metadata

### Before (Original MCP):
- ❌ Guessed field names
- ❌ Limited to ~20 fields
- ❌ Basic validation
- ❌ Generic search

### After (Metadata-Driven):
- ✅ **72 accurate property fields** from Tax_fields.json
- ✅ **7 assessment fields** from history_fields.json
- ✅ **Proper enums** for categorical data:
  - Category codes (1-6)
  - Basement types (0, A-J)
  - Exterior conditions (0-7)
  - Quality grades (1-5)
  - Garage types (0, A-D)
  - Heater types (0, A-H)
  - Fuel types (0, A-F)
- ✅ **Complete field descriptions** from metadata
- ✅ **Accurate validation** based on actual data
- ✅ **Enhanced search capabilities**

## 📊 Available Fields

### Properties Table (72 fields):

**Identification:**
- parcel_number, location, zip_code, census_tract, geographic_ward, unit

**Ownership:**
- owner_1, owner_2, mailing_address_1, mailing_address_2, mailing_care_of,
  mailing_city_state, mailing_street, mailing_zip

**Valuation:**
- market_value, market_value_date, assessment_date, taxable_land, taxable_building,
  exempt_land, exempt_building

**Physical Characteristics:**
- year_built, year_built_estimate, category_code, building_code,
  number_of_bedrooms, number_of_bathrooms, number_of_rooms, number_stories,
  total_area, total_livable_area, frontage, depth

**Quality & Condition:**
- quality_grade, exterior_condition, interior_condition, date_exterior_condition

**Features & Systems:**
- basements, garage_type, garage_spaces, central_air, fireplaces,
  type_heater, fuel, utility, separate_utilities

**Lot & Site:**
- shape, topography, site_type, view, sewer, off_street_open, other_building

**Sales:**
- sale_date, sale_price, recording_date, book_and_page

**Administrative:**
- zoning, building_code_description, category_code_description,
  general_construction, cross_reference, registry_number, state_code,
  street_code, street_name, street_designation, street_direction,
  house_number, house_extension, suffix, unfinished

### Assessment History Table (7 fields):
- parcel_number, year, market_value, taxable_land, taxable_building,
  exempt_land, exempt_building

## 🚀 Quick Start

### 1. Install Dependencies

```bash
# Activate your Anaconda environment
conda activate your_env_name

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

Create `.env` file:
```bash
# Copy template
cp .env.template .env

# Edit with your values
ANTHROPIC_API_KEY=sk-ant-xxxxx
MCP_SERVER_PATH=./philadelphia_property_census_mcp_metadata_driven.py
PYTHON_PATH=python  # or full path to Anaconda python
CENSUS_API_KEY=your_census_key  # Optional
```

### 3. Start Backend Server

```bash
python backend_server.py
```

Expected output:
```
============================================================
MCP-Claude API Backend Server
============================================================
MCP Server Path: ./philadelphia_property_census_mcp_metadata_driven.py
Python Path: python
Starting Flask server on http://localhost:5000
============================================================
```

### 4. Open Chatbot Interface

Open `chatbot_interface.html` in your browser. It connects to `localhost:5000`.

## 💬 Example Queries

Try asking:

**Basic Searches:**
- "Find properties in ZIP 19103"
- "Search for properties owned by John Smith"
- "Show me properties at 1234 Market Street"

**Advanced Searches:**
- "Find 3-bedroom properties in 19103 with central air and a garage"
- "Show me properties built after 1950 with quality grade A or B"
- "Find properties with basements, under $400,000, in good condition"
- "Search for properties with finished basements and 2+ fireplaces"

**Detailed Property Info:**
- "Get complete details for parcel 883309100"
- "Show me everything about parcel 123456789"

**Market Analysis:**
- "Show recent sales in ZIP 19107 in the last 6 months"
- "Find properties that sold for over $500,000 recently"
- "What are properties selling for in Center City?"

**Assessment History:**
- "Show assessment history for parcel 883309100"
- "How has the market value changed over the years?"

**Census Data:**
- "What are the demographics of Philadelphia County?"
- "Show me census data for ZIP 19103"
- "Compare demographics between Philadelphia and Montgomery County"

**Combined Queries:**
- "Find high-quality residential properties in areas with high median income"
- "Show me properties in the best condition in wealthy neighborhoods"

## 🏗️ Architecture

```
┌─────────────────────┐
│   Browser           │
│ (chatbot UI)        │
└──────────┬──────────┘
           │ HTTP POST
           ↓
┌─────────────────────┐
│  Backend Server     │
│  (Flask)            │
└──────────┬──────────┘
           │ Anthropic SDK
           ↓
┌─────────────────────┐
│  Claude API         │
│  (Sonnet 4.5)       │
└──────────┬──────────┘
           │ Tool Calls
           ↓
┌─────────────────────┐
│  MCP Server         │
│  (Metadata-Driven)  │
└──────────┬──────────┘
           │ SQL/HTTP
           ↓
┌─────────────────────┐
│  CARTO API          │
│  Census API         │
└─────────────────────┘
```

## 🔧 Tools Available

### Property Tools

1. **philly_search_properties**
   - Basic search by address, owner, parcel, ZIP
   - Returns: location, ownership, value, beds/baths, area, sale info

2. **philly_get_property_details**
   - Complete property details (all 72 fields)
   - Returns: everything about a specific property

3. **philly_search_by_characteristics**
   - Advanced search with multiple filters
   - Filters: beds, baths, area, year, quality, condition, features
   - Returns: matching properties sorted by value

4. **philly_search_recent_sales**
   - Find properties with recent sales
   - Filters: ZIP, price range, time period
   - Returns: sale date, price, property details

### Assessment Tools

5. **philly_search_assessments**
   - Historical assessment records
   - Filters: parcel, year, value range
   - Returns: year-by-year market values and taxes

### Census Tools

6. **census_get_demographics**
   - US Census demographic data
   - Filters: state, county, ZIP
   - Returns: population, age, race, households, income

## 📈 What Makes This Better

### 1. Accurate Field Names
No more guessing! Every field name matches the actual CARTO API.

**Before:**
```python
# Might not exist or be wrong
"number_bedrooms", "bed_count", "bedrooms"
```

**After:**
```python
# From metadata - guaranteed to work
"number_of_bedrooms"
```

### 2. Proper Enums

**Before:**
```python
quality_grade: Optional[str]  # Could be anything
```

**After:**
```python
class QualityGrade(str, Enum):
    LOW = "1"
    BELOW_AVERAGE = "2"
    AVERAGE = "3"
    ABOVE_AVERAGE = "4"
    EXCELLENT = "5"

quality_grade: Optional[QualityGrade]  # Type-safe!
```

### 3. Complete Field Coverage

**Before:** ~20 fields
**After:** All 72 fields from properties table

This means you can search/filter by:
- Basement type and finish
- Garage type and spaces
- Heater and fuel type
- Number of fireplaces
- View type
- Topography
- Interior condition
- Lot shape
- Zoning
- Census tract
- And 50+ more!

### 4. Better Descriptions

Every field has its official description from the metadata:

```python
quality_grade: "Building quality grade (1=Low, 2=Below Avg, 3=Avg, 4=Above Avg, 5=Excellent)"
```

### 5. Smart Validation

```python
@field_validator('zip_code')
def validate_zip(cls, v):
    if v and not v.startswith('19'):
        raise ValueError("Philadelphia ZIP codes start with '19'")
    return v
```

## 🎨 Features Comparison

| Feature | Original | Improved | Metadata-Driven |
|---------|----------|----------|-----------------|
| Property fields | ~15 | ~25 | ✅ **72** |
| Assessment fields | 7 | 7 | ✅ 7 |
| Accurate names | ❌ | ⚠️ Partial | ✅ **Yes** |
| Enums | ❌ Basic | ⚠️ Some | ✅ **Complete** |
| Field descriptions | ❌ Generic | ⚠️ Basic | ✅ **Official** |
| Rate limiting | ❌ | ✅ | ✅ |
| Error handling | ⚠️ Basic | ✅ Good | ✅ **Excellent** |
| Validation | ⚠️ Basic | ✅ Good | ✅ **Complete** |
| Search tools | 3 | 5 | ✅ **6** |

## 🐛 Troubleshooting

### "No module named 'fastmcp'"
```bash
pip install fastmcp
```

### "Connection refused" on chatbot
- Ensure backend server is running: `python backend_server.py`
- Check it's on port 5000: `http://localhost:5000/health`

### "API key invalid"
- Get key from: https://console.anthropic.com
- Add to `.env`: `ANTHROPIC_API_KEY=sk-ant-xxxxx`

### "No property found"
- Parcel numbers are 9 digits
- Remove dashes: Use `883309100` not `88-3309-100`

### MCP server won't start
- Check Python path in `.env`
- Verify MCP_SERVER_PATH points to the file
- Test: `python philadelphia_property_census_mcp_metadata_driven.py`

### Census API errors
- Get free key: https://api.census.gov/data/key_signup.html
- Pennsylvania FIPS: `42`
- Philadelphia County FIPS: `101`

## 📚 Resources

- [Anthropic API Docs](https://docs.anthropic.com)
- [MCP Documentation](https://modelcontextprotocol.io)
- [Philadelphia Open Data](https://www.opendataphilly.org)
- [Census API Guide](https://www.census.gov/data/developers.html)
- [CARTO SQL API](https://carto.com/developers/sql-api/)

## 🔐 Security Notes

- Never commit `.env` file
- Keep API keys secure
- For production, add authentication to backend
- Consider rate limiting on backend endpoints

## 🎓 Field Reference

### Category Codes
- 1 = Residential
- 2 = Hotels and Apartments
- 3 = Store with Dwelling
- 4 = Commercial
- 5 = Industrial
- 6 = Vacant Land

### Exterior Condition Codes
- 0 = Not Applicable
- 1 = Newer Construction
- 2 = Rehabilitated
- 3 = Above Average
- 4 = Average
- 5 = Below Average
- 6 = Vacant
- 7 = Sealed/Condemned

### Quality Grade Codes
- 1 = Low
- 2 = Below Average
- 3 = Average
- 4 = Above Average
- 5 = Excellent

### Basement Types
- 0 = None
- A = Full Finished
- B = Full Semi-Finished
- C = Full Unfinished
- D = Full Unknown Finish
- E = Partial Finished
- F = Partial Semi-Finished
- G = Partial Unfinished
- H = Partial Unknown Finish
- I = Unknown Size Finished
- J = Unknown Size Unfinished

## 🤝 Next Steps

Want to add more features? Consider:

1. **Batch operations** - Look up multiple properties at once
2. **Export to CSV** - Download search results
3. **Market analytics** - Aggregate statistics by neighborhood
4. **Comparison tools** - Compare multiple properties side-by-side
5. **Geospatial search** - Find properties within radius of lat/lon
6. **Price trends** - Analyze value changes over time
7. **Neighborhood profiles** - Combined property + census data

## 📝 License

This is a tool for accessing public Philadelphia property and US Census data.
Always respect API rate limits and terms of service.

---

**Built with:** FastMCP, Claude API, Flask, Philadelphia CARTO API, US Census Bureau API
