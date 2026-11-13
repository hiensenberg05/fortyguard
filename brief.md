# FortyGuard Temperature Intelligence® & MCP Evaluation Brief

**Evaluation Date:** November 13, 2026  
**Evaluator Environment:** Windows 11 | Python 3.13 Virtual Environment  
**LLM Engine:** Groq LPUs (`qwen/qwen3.8-27b`) & xAI Grok Compatible Client  
**MCP Gateway:** FortyGuard FastMCP Server (`https://tos-mcp.app.fortyguard.com/mcp`, Protocol `2024-11-05`)  
**Frontend Application:** Streamlit Interactive Geospatial Dashboard (`http://localhost:8501`)  

---

## 1. Executive Summary

We conducted an end-to-end evaluation of the **FortyGuard Temperature API®**, **Temperature Dashboard®**, and **Model Context Protocol (MCP)** gateway. As part of this assessment, we developed a production-ready autonomous thermal agent and interactive Streamlit frontend that connects directly to FortyGuard’s MCP tools to visualize urban thermal stress, atmospheric variables, and temperature-aware routing.

* **Overall Test Suite Result:** **10/10 Passed (100%)**
* **Overall Experience Rating:** **7 / 10**
* **Standout Capability:** **Temperature-Aware Routing** (`temperature_routing`). It uniquely identifies driving corridors optimized for reduced thermal exposure ($^\circ\text{C}\cdot\text{min}$ heat stress) versus raw travel speed.
* **Primary Friction Points:** Absence of a temperature color scale/legend on the dashboard, documentation divergence between REST and MCP endpoints, and high per-call credit consumption without a testing sandbox.

---

## 2. Technical Architecture & Implementation

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FortyGuard Thermal Studio                       │
│                                                                        │
│   ┌─────────────────────┐               ┌──────────────────────────┐   │
│   │   Streamlit UI      │◄─────────────►│  Autonomous AI Agent     │   │
│   │   (Folium / Plotly) │               │  Groq LPU / xAI Grok     │   │
│   └──────────┬──────────┘               └────────────┬─────────────┘   │
│              │                                       │                 │
│              │ GeoJSON & Charts                      │ Tool Calling    │
│              ▼                                       ▼                 │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │             FortyGuard MCP Client & Gateway Adapter            │   │
│   │   - US Bounding Box Pre-flight Checks (24.4°N-49.4°N)          │   │
│   │   - Asynchronous Job Submission & Auto-Polling Engine          │   │
│   │   - Credit Burn Guardrails & Unit Conversion Normalization     │   │
│   └──────────────────────────────┬─────────────────────────────────┘   │
│                                  │ JSON-RPC 2.0 / SSE Stream           │
│                                  ▼                                     │
│   ┌────────────────────────────────────────────────────────────────┐   │
│   │            FortyGuard Remote MCP Server / REST API             │   │
│   │            https://tos-mcp.app.fortyguard.com/mcp              │   │
│   └────────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────────┘
```

### Key Modules Developed:
1. **`fortyguard_mcp.py`**: Robust SSE streaming client for FastMCP (`v4.0.11`), supporting dynamic tool discovery, trace capturing, and automated polling (`submit` $\rightarrow$ `wait` $\rightarrow$ `read`).
2. **`rest_client.py`**: Direct REST client querying system credit usage, subscription states, and point metrics.
3. **`llm_agent.py`**: Autonomous agent orchestrating function calls between Groq/Grok LLMs and FortyGuard MCP tools.
4. **`app.py`**: Full-featured interactive Streamlit frontend featuring multi-route Folium mapping, microclimate gauge telemetry, and live agent chat.
5. **`test_suite.py` & `test_endpoints.py`**: Automated unit and benchmark suites measuring latency, boundary enforcement, and schema validation.

---

## 3. Empirical Benchmark & Test Execution Matrix

Our automated test suite evaluated FortyGuard across 4 geographic climate zones (Desert, Subtropical, Tropical, Arid) and boundary stress tests:

| Test Name | Target / Focus | Latency | Status | Key Observations |
| :--- | :--- | :---: | :---: | :--- |
| **REST: `fetch-api-key-usage`** | System usage & tier | 1,500 ms | ✅ PASS | Premium tier, 1,000,000 baseline credits verified. |
| **MCP: `tools/list` discovery** | Protocol handshake | 4,133 ms | ✅ PASS | Successfully discovered all 11 enterprise MCP tools. |
| **MCP: `env_params` (Phoenix)** | Desert climate ($38^\circ\text{C}$) | 9,324 ms | ✅ PASS | Heat index ($37.3^\circ\text{C}$), Wet-bulb ($23.7^\circ\text{C}$), AQI ($58.4$). |
| **MCP: `env_params` (Austin)** | Subtropical climate ($34^\circ\text{C}$) | 6,598 ms | ✅ PASS | Solar irradiance profile (GHI/DNI/DHI) & AQI returned. |
| **MCP: `env_params` (Miami)** | Coastal humidity ($31^\circ\text{C}$) | 7,821 ms | ✅ PASS | Surface relative humidity & wet-bulb profile retrieved. |
| **MCP: `env_params` (Las Vegas)** | Arid heat island ($40^\circ\text{C}$) | 7,129 ms | ✅ PASS | Atmospheric pressure & apparent temperature retrieved. |
| **MCP: `temperature_routing`** | Multi-route async cycle | 24,318 ms | ✅ PASS | Generated 4 routes in 18.03s poll time with GeoJSON geometries. |
| **Security: Bounds Check** | International (Dubai) | < 1 ms | ✅ PASS | Correctly rejected coordinates outside contiguous US. |
| **Validation: Missing Inputs** | Schema error handling | 2,428 ms | ✅ PASS | Accurately caught missing required parameters. |
| **Agent: Autonomous Loop** | Groq + Tool Execution | 5,309 ms | ✅ PASS | LLM autonomously invoked `credit_balance` & synthesized answer. |

---

## 4. Temperature-Aware Routing Deep Dive

The routing engine proved to be the most compelling feature. In our live test corridor in Phoenix, AZ, FortyGuard returned **4 distinct GeoJSON routes** comparing thermal exposure against travel duration:

* **Route 1 (Fastest):** Distance: $10.67\text{ km}$ | Time: $8.34\text{ min}$ | Mean Temp: $35.82^\circ\text{C}$ | Peak Temp: $36.07^\circ\text{C}$ | Exposure: $31.6^\circ\text{C}\cdot\text{min}$ above $32^\circ\text{C}$.
* **Route 2 (Balanced):** Distance: $10.00\text{ km}$ | Time: $9.70\text{ min}$ | Mean Temp: $35.79^\circ\text{C}$ | Peak Temp: $36.07^\circ\text{C}$ | Exposure: $36.76^\circ\text{C}\cdot\text{min}$.
* **Route 3 (Option 4):** Distance: $9.99\text{ km}$ | Time: $9.78\text{ min}$ | Mean Temp: $35.79^\circ\text{C}$ | Peak Temp: $36.07^\circ\text{C}$ | Exposure: $37.06^\circ\text{C}\cdot\text{min}$.
* **Route 4 (Coolest):** Distance: $9.91\text{ km}$ | Time: $11.11\text{ min}$ | Mean Temp: $35.76^\circ\text{C}$ | Peak Temp: $36.04^\circ\text{C}$ | Lower average thermal intensity.

*Takeaway:* The engine successfully balances travel efficiency against microclimate heat exposure, an essential tool for fleet management, cold-chain transport, and urban heat mitigation.

---

## 5. Dashboard Evaluation (UI & UX)

### Strengths:
1. **Clean GIS Baseline:** Smooth integration with Google Maps satellite layers and responsive collapsible side panels.
2. **Actionable Monitor Configuration:** Thoughtful workflow allowing users to set recurring temperature checks on saved heatmaps, target sub-polygons, and generate automated PDF alerts.
3. **Direct Navigation Integration:** Prominently surfacing "Find the Coolest Route" directly in the GIS dashboard.

### Weaknesses & Confusing Behaviors:
1. **Absence of a Color Legend / Scale:** The circular heatmap displays colors from dark blue to dark red, but **has no temperature scale or legend on screen**. Users cannot tell what temperature any color represents.
2. **Artificial Circular Gradient:** Heatmaps are displayed as strict geometric circles with an unnatural North-to-South linear gradient, rather than conforming to genuine urban topography (e.g., hot asphalt freeways vs. cooler tree canopy or rivers).
3. **Passive Cells (No Tooltips):** Clicking or hovering over heatmap cells does not surface localized metrics.
4. **Viewport Squeeze:** Opening the left activity navigation drawer plus the configuration drawer consumes over $45\%$ of screen width on $1080\text{p}$ monitors, compressing the map.
5. **Redundant Search Bars:** Two separate search bars ("Go to... City, street..." on map vs. "Search Activity..." on the sidebar) create navigation ambiguity.

---

## 6. API & MCP Gateway Evaluation

### Strengths:
1. **Modern MCP Standard:** Clean FastMCP implementation using standard JSON-RPC 2.0 streaming via Server-Sent Events (SSE).
2. **Comprehensive Tool Schemas:** Tools contain descriptive parameter schemas, min/max bounds, and explicit credit cost warnings for LLMs.
3. **Multi-Parameter Atmosphere Data:** Delivers wet-bulb temperature, apparent temperature, AQI components ($\text{PM2.5}, \text{PM10}, \text{NO}_2, \text{SO}_2, \text{O}_3, \text{CO}$), and solar irradiance splits ($\text{GHI}, \text{DNI}, \text{DHI}$).

### Weaknesses & Friction Points:
1. **REST vs. MCP Endpoint Drift:** Calling `POST /v1/temperature_routing` returned `404 Endpoint not found` on the REST gateway, while working smoothly via the MCP gateway.
2. **Redundant Payload in REST Usage API:** `POST /v1/system/fetch-api-key-usage` throws HTTP 422 if `{"api_key": "..."}` is not provided in the JSON body, even though the `api-key` header is present.
3. **Temperature Unit Discrepancies:** `env_params` requires Celsius ($^\circ\text{C}$), whereas the `report` tool prompt schema specifies Fahrenheit ($^\circ\text{F}$).
4. **Asynchronous Polling Overhead:** Async tools return an `activity_id` and require repetitive polling on `_read` tools rather than supporting a streamed terminal response.
5. **Credit Burn Rate in Autonomous Loops:** Analytical operations cost between 2,900 and 14,400 credits per call. Without a zero-credit dry-run mode, an uncontrolled agent loop can exhaust enterprise quotas rapidly.

---

## 7. Top Recommendations for the FortyGuard Team

1. **Add a Floating Dynamic Legend & Point Inspector to Dashboard:** Provide a docked color bar with min/max values ($^\circ\text{C}$ / $^\circ\text{F}$) and enable click/hover tooltips on grid cells.
2. **Conform Heatmaps to Real Urban Geometry:** Transition from rigid circular raster disks to realistic urban polygon masks that visually reflect highway heat corridors and vegetated cooling islands.
3. **Unify Unit Standards Across Endpoints:** Standardize all input and output temperature parameters to SI units ($^\circ\text{C}$).
4. **Provide a Zero-Credit Dry-Run Sandbox:** Enable a sandbox mode for developers and AI agents to validate tool-calling schemas without deducting production credits.
5. **Support Interactive Map-Click Routing:** Allow users to drop Start and Destination pins directly onto the map canvas rather than relying solely on text address geocoding.
