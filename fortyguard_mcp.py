import json
import time
import requests
from typing import Dict, Any, List, Optional, Tuple
from config import (
    FORTY_GUARD_API_KEY,
    FORTY_GUARD_MCP_URL,
    TOOL_CREDIT_COSTS,
    is_within_us_bounds,
)

class FortyGuardMCPClient:
    """
    Robust client for FortyGuard Model Context Protocol (MCP) server.
    Operates over Streamable HTTP SSE (2024-11-05 standard).
    """

    def __init__(self, api_key: Optional[str] = None, mcp_url: str = FORTY_GUARD_MCP_URL):
        self.api_key = api_key or FORTY_GUARD_API_KEY
        self.mcp_url = mcp_url
        self._tools_cache: Optional[List[Dict[str, Any]]] = None

    @property
    def headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    def _parse_sse(self, text: str) -> Dict[str, Any]:
        """Extract and parse JSON payload from SSE event stream."""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                json_str = line[5:].strip()
                try:
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    pass
        try:
            return json.loads(text)
        except Exception:
            raise ValueError(f"Unable to parse SSE response: {text[:200]}")

    def initialize(self) -> Dict[str, Any]:
        """Handshake with FortyGuard MCP server."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "fortyguard-studio", "version": "1.0"},
            },
        }
        res = requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=15)
        res.raise_for_status()
        return self._parse_sse(res.text)

    def list_tools(self, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Discover available MCP tools."""
        if self._tools_cache and not force_refresh:
            return self._tools_cache

        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {},
        }
        res = requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=20)
        res.raise_for_status()
        data = self._parse_sse(res.text)
        self._tools_cache = data.get("result", {}).get("tools", [])
        return self._tools_cache

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute an MCP tool call and return structured content and traces.
        """
        payload = {
            "jsonrpc": "2.0",
            "id": int(time.time() * 1000) % 1000000,
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments,
            },
        }
        start_time = time.time()
        res = requests.post(self.mcp_url, headers=self.headers, json=payload, timeout=40)
        latency_ms = int((time.time() - start_time) * 1000)

        if res.status_code != 200:
            return {
                "ok": False,
                "error": f"HTTP {res.status_code}: {res.text[:300]}",
                "latency_ms": latency_ms,
            }

        parsed = self._parse_sse(res.text)
        if "error" in parsed:
            return {
                "ok": False,
                "error": parsed["error"],
                "latency_ms": latency_ms,
            }

        result_payload = parsed.get("result", {})
        structured = result_payload.get("structuredContent")

        # Fallback to parsing text content
        if not structured and "content" in result_payload:
            for item in result_payload["content"]:
                if item.get("type") == "text":
                    try:
                        inner = json.loads(item.get("text", "{}"))
                        structured = inner.get("result", {}).get("value") or inner.get("result") or inner
                        break
                    except Exception:
                        structured = {"raw_text": item.get("text")}

        return {
            "ok": not result_payload.get("isError", False),
            "data": structured,
            "raw": result_payload,
            "latency_ms": latency_ms,
            "estimated_cost": TOOL_CREDIT_COSTS.get(name, 0),
        }

    # --- High-level Workflow Helpers ---

    def get_credit_balance(self) -> Dict[str, Any]:
        """Fetch real-time enterprise credit balance."""
        res = self.call_tool("credit_balance", {})
        if res["ok"] and res.get("data"):
            credits = res["data"].get("available_credits")
            return {"ok": True, "available_credits": credits, "raw": res}
        return {"ok": False, "error": res.get("error", "Failed to retrieve balance")}

    def get_env_params(
        self,
        latitude: float,
        longitude: float,
        temperature: float,
        date_str: str,
        time_str: str = "12:00",
        filter_type: int = 1,
    ) -> Dict[str, Any]:
        """
        Query point-level environmental metrics (heat index, wet bulb, AQI, solar irradiance).
        Validates US bounding box before dispatching.
        """
        # Auto-correct flipped US longitudes (e.g. 112.074 -> -112.074)
        if 65.0 <= longitude <= 130.0:
            longitude = -abs(longitude)

        if not is_within_us_bounds(latitude, longitude):
            return {
                "ok": False,
                "error": f"Location ({latitude}, {longitude}) is outside supported contiguous US coverage.",
            }

        args = {
            "latitude": latitude,
            "longitude": longitude,
            "temperature": temperature,
            "date_time": {
                "start_date": date_str,
                "start_time": time_str,
                "filter_type": filter_type,
            },
        }
        return self.call_tool("env_params", args)

    def get_temperature_routing(
        self,
        origin: Dict[str, float],
        destination: Dict[str, float],
        departure_time: str,
        max_poll_sec: int = 30,
    ) -> Dict[str, Any]:
        """
        Submit a temperature-aware routing request and poll temperature_routing_read until complete.
        Returns GeoJSON routes with thermal analytics (Fastest, Coolest, Balanced).
        """
        # Auto-correct flipped US longitudes
        if 65.0 <= origin.get("lon", 0) <= 130.0:
            origin["lon"] = -abs(origin["lon"])
        if 65.0 <= destination.get("lon", 0) <= 130.0:
            destination["lon"] = -abs(destination["lon"])

        # Validate US bounds for origin and destination
        if not is_within_us_bounds(origin["lat"], origin["lon"]):
            return {"ok": False, "error": f"Origin ({origin['lat']}, {origin['lon']}) is outside US bounds."}
        if not is_within_us_bounds(destination["lat"], destination["lon"]):
            return {"ok": False, "error": f"Destination ({destination['lat']}, {destination['lon']}) is outside US bounds."}

        # Step 1: Submit routing job
        submit_res = self.call_tool("temperature_routing", {
            "origin": {"lat": origin["lat"], "lon": origin["lon"]},
            "destination": {"lat": destination["lat"], "lon": destination["lon"]},
            "departure_time": departure_time,
        })

        if not submit_res["ok"]:
            return submit_res

        # Extract activity_id from nested result
        activity_id = None
        data = submit_res.get("data", {})
        if isinstance(data, dict):
            res_dict = data.get("result", {})
            if isinstance(res_dict, dict):
                activity_id = res_dict.get("activity_id") or res_dict.get("value", {}).get("activity_id")
            if not activity_id:
                activity_id = data.get("activity_id")

        if not activity_id:
            raw_text = submit_res.get("raw", {}).get("content", [{}])[0].get("text", "")
            try:
                inner = json.loads(raw_text)
                activity_id = inner.get("result", {}).get("activity_id") or inner.get("result", {}).get("value", {}).get("activity_id") or inner.get("activity_id")
            except Exception:
                pass

        if not activity_id:
            return {"ok": False, "error": "No activity_id returned from routing submission", "details": submit_res}

        # Step 2: Poll temperature_routing_read
        start_time = time.time()
        while time.time() - start_time < max_poll_sec:
            poll_res = self.call_tool("temperature_routing_read", {"activity_id": activity_id})
            if poll_res["ok"] and poll_res.get("data"):
                data_dict = poll_res["data"]
                res_obj = data_dict.get("result", {}) if isinstance(data_dict, dict) else {}
                val = res_obj.get("value", {}) if isinstance(res_obj, dict) else data_dict
                if not isinstance(val, dict):
                    val = data_dict

                status = (val.get("status") or "").lower()
                if status == "completed":
                    routes = val.get("routes", [])
                    return {
                        "ok": True,
                        "activity_id": activity_id,
                        "routes": routes,
                        "total_poll_time_sec": round(time.time() - start_time, 2),
                    }
                elif status in ["failed", "error"]:
                    return {"ok": False, "error": f"Routing failed with status: {status}", "data": val}

            time.sleep(2)

        return {"ok": False, "error": f"Routing timed out after {max_poll_sec} seconds", "activity_id": activity_id}
