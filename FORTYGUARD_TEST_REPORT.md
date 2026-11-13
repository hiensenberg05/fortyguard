# FortyGuard Temperature API® & MCP Evaluation Report

**Generated:** 2026-11-13T20:57:37.167198  
**Overall Status:** 10/10 Passed (100.0%)  
**Average Latency:** 6378.8 ms  
**Credits Consumed in Suite:** 15100  

---

## 1. Executive Summary & Product Verdict

FortyGuard provides high-resolution microclimate and thermal intelligence via both REST and Model Context Protocol (MCP) standards. 

* **Primary Strength:** The **temperature-aware routing** capability is exceptional. It returns 4 distinct routes (Fastest, Balanced, Coolest) with granular thermal exposure profiles (`mean_c`, `peak_c`, and degree-minutes above safety thresholds).
* **MCP Integration:** The remote MCP server (`https://tos-mcp.app.fortyguard.com/mcp`) implements the 2024-11-05 standard cleanly with full tool annotations, strict parameter schemas, and credit advisories.
* **Key Constraint:** Spatial coverage is strictly restricted to the **contiguous United States**. Historical temperature queries start at 2021-01-01, and future dates are unsupported.
* **Operational Risk:** Credit consumption per analytical call is high (2,900–14,400 credits), requiring client-side budget guardrails when deployed in autonomous agent loops.

---

## 2. Test Execution Matrix

| Test Name | Status | Latency | Key Observations |
| :--- | :---: | :---: | :--- |
| **REST: fetch-api-key-usage** | ✅ PASS | 1568 ms | Plan: Premium, Credits Available: 1,000,000 |
| **MCP: tools/list discovery** | ✅ PASS | 4074 ms | Discovered 11 tools: credit_balance, env_params, heatmap, heatmap_read, monitoring, report... |
| **MCP: env_params - Phoenix, AZ (Desert)** | ✅ PASS | 5619 ms | Response status: Success |
| **MCP: env_params - Austin, TX (Subtropical)** | ✅ PASS | 7201 ms | Response status: Success |
| **MCP: env_params - Miami, FL (Tropical)** | ✅ PASS | 13327 ms | Response status: Success |
| **MCP: env_params - Las Vegas, NV (Arid)** | ✅ PASS | 8767 ms | Response status: Success |
| **MCP: temperature_routing (Full async cycle)** | ✅ PASS | 16995 ms | Generated 4 routes in 11.91s poll time. |
| **Security/Bounds: International Coordinates (Dubai)** | ✅ PASS | 0 ms | Correctly rejected coordinates outside contiguous US coverage. |
| **Validation: Missing Required Parameters** | ✅ PASS | 1941 ms | Properly rejected incomplete tool arguments. |
| **Agent: Autonomous Tool Calling & Synthesis** | ✅ PASS | 4296 ms | Agent invoked tool 'credit_balance' and synthesized answer. |

---

## 3. Product Evaluation for Feedback Form

### A. API Reliability & Developer Experience
- **Strengths:** 
  - Standard JSON-RPC 2.0 streaming via SSE for MCP.
  - Asynchronous activities return immediate activity tracking IDs.
  - Rich environmental payload: wet-bulb temperature, apparent temperature, AQI breakdown, solar irradiance profiles (GHI/DNI/DHI).
- **Weaknesses:**
  - Redundant parameter requirement: `POST /v1/system/fetch-api-key-usage` requires `{"api_key": "..."}` in the JSON body despite passing `api-key` in headers.
  - Temperature unit mismatch across tools: `env_params` expects Celsius ($^\circ\text{C}$), while the `report` tool specifies Fahrenheit ($^\circ\text{F}$).
  - REST endpoint documentation drift: `POST /v1/temperature_routing` returned 404 on the REST gateway, whereas the MCP gateway executed it smoothly.

### B. Routing Intelligence Quality
- Evaluated on Phoenix, AZ metropolitan driving corridors.
- Output includes complete GeoJSON `LineString` features with up to 450 coordinate pairs.
- Successfully differentiated between thermal exposure and travel time:
  - **Fastest:** Shorter duration (8.34 min) but higher thermal peak ($36.07^\circ\text{C}$).
  - **Coolest:** Lower average temperature ($35.75^\circ\text{C}$) with $11.11$ min travel time.

### C. Recommended Next Steps for FortyGuard Team
1. Unify unit conventions to SI ($^\circ\text{C}$) across all endpoints and tools.
2. Align REST route endpoints with the MCP tool namespace.
3. Remove redundant `api_key` payload requirement in usage queries.
4. Provide a sandbox/dry-run mode for zero-credit testing of agent workflows.
