# Fels Public AI Lab — MCP Servers

Model Context Protocol (MCP) server development for the Fels Public AI Lab 
(FPAL) at the Fels Institute of Government, University of Pennsylvania.

🌐 **Lab website:** [fels-public-ai-lab.github.io](https://fels-public-ai-lab.github.io)

## About

This repository contains MCP servers developed by FPAL to make public sector 
data genuinely accessible through AI interfaces. MCP (Model Context Protocol) 
allows AI assistants to connect directly to external data sources 
and APIs, enabling natural language interaction with government data systems.

## Servers

| Server | Description | Status |
|--------|-------------|--------|
| Philadelphia Property Tax | Connects to Philadelphia's property assessment and tax data via the CARTO API | Active |

## Getting Started

### Prerequisites
- Any MCP-compatible AI client (Claude Desktop, Cursor, Copilot Studio, etc.)
- Node.js (v18 or higher) or Python 3.10+

### Installation
Each server has its own directory with setup instructions. See the README
in each subdirectory for configuration details.

### Connecting to an MCP Client
Add the server configuration to your client's MCP config file. Example:
```json
{
  "mcpServers": {
    "server-name": {
      "command": "node",
      "args": ["/path/to/server/index.js"]
    }
  }
}
```

Refer to your client's documentation for the specific configuration path 
and format.

## Research Context

These servers support FPAL's research into AI-enabled civic transparency.
Our flagship project — the Philadelphia Property Tax MCP Server —
demonstrates how AI can transform open government data from technically
available to genuinely accessible, particularly for property assessment
equity analysis and tax appeal preparation.

## Contact

📧 [publicailab@sas.upenn.edu](mailto:publicailab@sas.upenn.edu)  
🏛️ Fels Institute of Government, University of Pennsylvania

---

© 2026 Fels Public AI Lab — MIT License
