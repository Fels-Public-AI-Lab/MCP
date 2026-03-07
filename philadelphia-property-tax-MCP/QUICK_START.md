# Quick Start Guide - Metadata-Driven MCP Server

## 🚀 5-Minute Setup

### Step 1: Install Dependencies (1 minute)
```bash
pip install -r requirements.txt
```

### Step 2: Create .env File (1 minute)
```bash
# Copy template
cp .env.template .env

# Edit .env with your text editor and add:
ANTHROPIC_API_KEY=sk-ant-your_key_here
MCP_SERVER_PATH=./philadelphia_property_census_mcp_metadata_driven.py
PYTHON_PATH=python
```

Get your Anthropic API key: https://console.anthropic.com

### Step 3: Start Backend (1 minute)
```bash
python backend_server.py
```

You should see:
```
MCP-Claude API Backend Server
Starting Flask server on http://localhost:5000
```

### Step 4: Open Chatbot (1 minute)
Double-click `chatbot_interface.html` or open it in your browser.

### Step 5: Try It! (1 minute)
Click a suggestion chip or type:
```
Find 3-bedroom properties in zip code 19103 with finished basements
```

## 🎯 What Makes This Version Special

### Built from Real Metadata
- **72 accurate property fields** from Tax_fields.json
- **7 assessment fields** from history_fields.json
- Every field name verified against CARTO API
- Official descriptions and valid values

### Advanced Search Capabilities

**Basic searches:**
```
Find properties in 19103
Show me 3-bedroom homes
Properties owned by John Smith
```

**Advanced searches (now possible with metadata!):**
```
Find properties with finished basements and central air
Show me quality grade A properties with attached garages
Properties with 2+ fireplaces in above-average condition
Find homes with hot water heat and natural gas fuel
```

**Feature-rich searches:**
```
Find 3-bed, 2-bath properties with:
- Finished basement
- 2+ car garage
- Central air
- Quality grade A or B
- Built after 1950
- Under $400,000
```

## 📊 Available Search Filters

Thanks to metadata, you can now filter by:

**Property Basics:**
- Bedrooms, bathrooms, rooms, stories
- Total area, livable area
- Year built, age range
- ZIP code, location

**Quality & Condition:**
- Quality grade (1-5)
- Exterior condition (0-7)
- Interior condition
- Basement type (11 options!)

**Features:**
- Central air (Y/N)
- Fireplaces (count)
- Garage type (5 options)
- Garage spaces (count)
- Basement finish level

**Systems:**
- Heater type (8 options)
- Fuel type (7 options)
- Utilities configuration

**Lot & Site:**
- Topography
- View type
- Lot shape
- Frontage/depth

**Value & Sales:**
- Market value range
- Sale price range
- Recent sales (last N months)

**Administrative:**
- Property category (6 types)
- Zoning
- Building code
- Census tract

## 🛠️ Available Tools

### 1. philly_search_properties
Basic property search by address, owner, parcel, or ZIP.

Example:
```
Find properties at 1234 Market Street
Show me properties owned by Smith
```

### 2. philly_get_property_details
Complete details for a specific parcel (all 72 fields!).

Example:
```
Get details for parcel 883309100
Show me everything about parcel 123456789
```

### 3. philly_search_by_characteristics
Advanced multi-filter search.

Example:
```
Find properties with 3+ beds, 2+ baths, finished basement, 
garage, central air, quality grade A, in 19103, under $500k
```

### 4. philly_search_recent_sales
Find properties with recent sales.

Example:
```
Show recent sales in 19107 in the last 6 months
Find properties that sold for over $500,000 recently
```

### 5. philly_search_assessments
Historical assessment data by year.

Example:
```
Show assessment history for parcel 883309100
How has the value changed over time?
```

### 6. census_get_demographics
US Census demographic data.

Example:
```
What are the demographics of Philadelphia County?
Show me census data for ZIP 19103
Compare Philadelphia to Montgomery County
```

## 💡 Pro Tips

### 1. Use Specific Criteria
Instead of:
```
Find nice properties
```

Try:
```
Find properties with quality grade A or B, above average condition, 
finished basement, and central air
```

### 2. Combine Property + Census Data
```
Find high-quality properties in areas with median income over $75,000
Show me 3-bedroom homes in neighborhoods with good schools
```

### 3. Market Analysis
```
Show recent sales in 19103 by quality grade
What's the average sale price for properties with garages?
Find undervalued properties (market value vs recent sales)
```

### 4. Investment Research
```
Find vacant land in commercial zones
Show me multi-unit properties with separate utilities
Properties in flood plains (for insurance assessment)
```

## 📁 File Overview

**Main MCP Server:**
- `philadelphia_property_census_mcp_metadata_driven.py` ⭐ Use this one!

**Supporting Files:**
- `backend_server.py` - Claude API integration
- `chatbot_interface.html` - Web UI
- `requirements.txt` - Dependencies
- `.env.template` - Configuration template

**Documentation:**
- `README_METADATA.md` - Complete documentation
- `METADATA_IMPACT.md` - Before/after comparison
- `QUICK_START.md` - This file

## 🐛 Common Issues

### "Module not found: fastmcp"
```bash
pip install fastmcp
```

### "Connection refused"
Make sure backend is running:
```bash
python backend_server.py
```

### "Invalid API key"
Check your `.env` file has correct key from console.anthropic.com

### "No properties found"
- Check parcel numbers have no dashes: `883309100` not `88-3309-100`
- Verify ZIP codes: Philadelphia uses 191xx
- Some filters may be too restrictive - try fewer criteria

### Backend won't start
Check your Python path:
```bash
which python  # On Mac/Linux
where python  # On Windows
```

Update `PYTHON_PATH` in `.env` if needed.

## 📚 Learn More

### Field Reference
See `README_METADATA.md` for:
- Complete list of 72 property fields
- Enum value definitions
- Category codes
- Condition codes
- Search examples

### Metadata Impact
See `METADATA_IMPACT.md` for:
- Before/after comparison
- Specific improvements
- New capabilities unlocked
- Real-world use cases

## 🎓 Example Session

**User:** "Hi! I'm looking for a home in Philadelphia."

**Claude:** "I can help you search Philadelphia properties! What are you looking for?"

**User:** "3 bedrooms, 2 bathrooms, with a finished basement and garage, under $400,000"

**Claude:** [Uses philly_search_by_characteristics with filters:
- min_bedrooms: 3
- min_bathrooms: 2
- basement_type: FULL_FINISHED or PARTIAL_FINISHED
- garage_type: not NONE
- max_market_value: 400000]

**User:** "Show me the complete details for the first property"

**Claude:** [Uses philly_get_property_details with parcel number]

**User:** "What are the demographics of that ZIP code?"

**Claude:** [Uses census_get_demographics with ZIP code]

**User:** "Has this property value gone up over time?"

**Claude:** [Uses philly_search_assessments with parcel number]

## 🎯 Next Steps

Once you're comfortable with basic searches, try:

1. **Complex queries** - Combine multiple filters
2. **Market analysis** - Aggregate statistics
3. **Neighborhood research** - Property + census data
4. **Investment screening** - Find opportunities
5. **Comparative analysis** - Compare similar properties

## 🤝 Support

If you need help:
1. Check the README files
2. Review the metadata JSON files
3. Test with simple queries first
4. Check backend console for errors
5. Verify API keys are correct

## 🎉 You're Ready!

Your metadata-driven MCP server is now ready to provide accurate, comprehensive Philadelphia property data through a beautiful chatbot interface powered by Claude!

Happy searching! 🏠
