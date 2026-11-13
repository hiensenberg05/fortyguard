import json
import os
import re
from typing import Dict, Any, List, Optional
from config import (
    GROQ_API_KEY,
    GROK_API_KEY,
    DEFAULT_GROQ_MODEL,
    DEFAULT_GROK_MODEL,
)
from fortyguard_mcp import FortyGuardMCPClient

class ThermalAgent:
    """
    Intelligent Agent powered by Grok (xAI) or Groq LPUs,
    orchestrating tool-calling via the FortyGuard MCP Gateway.
    Includes token payload compression to avoid 413 rate limits.
    """

    def __init__(
        self,
        provider: str = "groq",
        model: Optional[str] = None,
        mcp_client: Optional[FortyGuardMCPClient] = None,
    ):
        self.provider = provider.lower()
        self.mcp = mcp_client or FortyGuardMCPClient()

        if self.provider == "grok":
            from openai import OpenAI
            api_key = GROK_API_KEY or os.getenv("XAI_API_KEY", "")
            if not api_key:
                raise ValueError("GROK_API_KEY or XAI_API_KEY must be set to use Grok provider.")
            self.client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
            self.model = model or DEFAULT_GROK_MODEL
        else:
            from groq import Groq
            api_key = GROQ_API_KEY
            if not api_key:
                raise ValueError("GROQ_API_KEY must be set to use Groq provider.")
            self.client = Groq(api_key=api_key)
            self.model = model or DEFAULT_GROQ_MODEL

        self.system_prompt = (
            "You are the FortyGuard Thermal Intelligence Agent, an expert in urban heat islands, "
            "microclimates, atmospheric parameters, and temperature-aware routing.\n\n"
            "CRITICAL RULES:\n"
            "1. US Longitudes are ALWAYS negative (between -66.9 and -125.0). For example: "
            "Phoenix is -112.0740, Austin is -97.7431, Miami is -80.1918. NEVER strip the minus sign or provide positive longitude for US locations.\n"
            "2. FortyGuard ONLY supports locations in the contiguous United States.\n"
            "3. When users ask for route planning with thermal considerations, use the 'temperature_routing' tool.\n"
            "4. When users ask about environmental metrics, apparent temperature, wet-bulb temp, AQI, or solar irradiance, use 'env_params'.\n"
            "5. If a tool call is executed, summarize findings clearly with specific numbers and actionable takeaways."
        )

    def _get_mcp_tools_definitions(self) -> List[Dict[str, Any]]:
        """Canonical FortyGuard MCP tool schemas for LLM tool calling."""
        return [
            {
                "type": "function",
                "function": {
                    "name": "credit_balance",
                    "description": "Check available FortyGuard Enterprise API credits (Free).",
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "env_params",
                    "description": "Get point-level environmental metrics: heat index, apparent temp, wet-bulb temp, relative humidity, AQI, and solar irradiance. Longitudes in the US are always negative (e.g. -112.0740).",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number", "description": "Decimal latitude (24.4 to 49.4)"},
                            "longitude": {"type": "number", "description": "Decimal longitude (-125.0 to -66.9, MUST be negative)"},
                            "temperature": {"type": "number", "description": "Ambient temperature in Celsius"},
                            "date_str": {"type": "string", "description": "Date in YYYY-MM-DD (e.g. 2024-07-15)"},
                            "time_str": {"type": "string", "description": "Local 24h wall time in HH:MM (e.g. 14:00)", "default": "12:00"},
                        },
                        "required": ["latitude", "longitude", "temperature", "date_str"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "temperature_routing",
                    "description": "Submit temperature-aware route generation between origin and destination coordinates in the US. Longitudes MUST be negative (e.g. -112.074). Returns multiple routes (Fastest, Coolest, Balanced) with thermal exposure metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin_lat": {"type": "number", "description": "Origin latitude (24.4 to 49.4)"},
                            "origin_lon": {"type": "number", "description": "Origin longitude (-125.0 to -66.9, MUST be negative)"},
                            "dest_lat": {"type": "number", "description": "Destination latitude (24.4 to 49.4)"},
                            "dest_lon": {"type": "number", "description": "Destination longitude (-125.0 to -66.9, MUST be negative)"},
                            "departure_time": {"type": "string", "description": "ISO-8601 departure timestamp (e.g. 2024-07-15T14:00:00Z)"},
                        },
                        "required": ["origin_lat", "origin_lon", "dest_lat", "dest_lon", "departure_time"],
                    },
                },
            },
        ]

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool calls to MCP client with safe coordinate auto-correction and fuzzy name matching."""
        def fix_lon(lon):
            if isinstance(lon, (int, float)) and 65.0 <= lon <= 130.0:
                return -abs(lon)
            return lon

        if "longitude" in args:
            args["longitude"] = fix_lon(args["longitude"])
        if "origin_lon" in args:
            args["origin_lon"] = fix_lon(args["origin_lon"])
        if "dest_lon" in args:
            args["dest_lon"] = fix_lon(args["dest_lon"])

        name_clean = name.lower()
        if "balance" in name_clean or "credit" in name_clean:
            return self.mcp.get_credit_balance()

        elif "env" in name_clean:
            return self.mcp.get_env_params(
                latitude=args.get("latitude", 33.4484),
                longitude=args.get("longitude", -112.0740),
                temperature=args.get("temperature", 35.0),
                date_str=args.get("date_str", "2024-07-15"),
                time_str=args.get("time_str", "12:00"),
            )

        elif "routing" in name_clean or "route" in name_clean:
            origin = {"lat": args.get("origin_lat", 33.4484), "lon": args.get("origin_lon", -112.0740)}
            dest = {"lat": args.get("dest_lat", 33.5092), "lon": args.get("dest_lon", -112.0362)}
            return self.mcp.get_temperature_routing(
                origin=origin,
                destination=dest,
                departure_time=args.get("departure_time", "2024-07-15T14:00:00Z"),
            )

        return {"ok": False, "error": f"Unknown tool: {name}"}

    def _compress_for_llm(self, name: str, result: Dict[str, Any]) -> str:
        """
        Compress tool result for LLM input to strictly prevent blowing token limits.
        Strips thousands of raw GeoJSON coordinates while retaining thermal summary.
        """
        name_lower = name.lower()
        if "routing" in name_lower or "route" in name_lower or "routes" in result:
            routes = result.get("routes", [])
            summary_list = []
            for r in routes:
                p = r.get("properties", {})
                summary_list.append({
                    "label": p.get("label"),
                    "distance_km": p.get("distance_km"),
                    "duration_min": p.get("duration_min"),
                    "thermal": p.get("thermal"),
                })
            compressed = {
                "ok": True,
                "activity_id": result.get("activity_id"),
                "total_routes": len(routes),
                "routes": summary_list,
                "note": "GeoJSON coordinate lines are rendered directly on the UI map.",
            }
            return json.dumps(compressed)

        # General guard for any response: keep within 2000 characters
        raw_json = json.dumps(result)
        if len(raw_json) > 2000:
            return json.dumps({
                "ok": result.get("ok", True),
                "summary": str(result.get("data", result))[:1500],
                "note": "Payload summarized to respect model token limits."
            })
        return raw_json

    def chat(self, user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Execute an agent turn with multi-step tool execution loop.
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if chat_history:
            # Keep only the last 4 messages to avoid token bloat across turns
            messages.extend(chat_history[-4:])
        messages.append({"role": "user", "content": user_message})

        tools = self._get_mcp_tools_definitions()
        executed_tool_traces = []
        artifacts = {}
        final_text = ""

        for iteration in range(3):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    temperature=0.2,
                )
            except Exception as e:
                # If tool call fails with a validation error, fall back to plain text answer
                err_str = str(e)
                if "tool_use_failed" in err_str or "400" in err_str:
                    fallback_resp = self.client.chat.completions.create(
                        model=self.model,
                        messages=messages,
                        temperature=0.3,
                    )
                    final_text = fallback_resp.choices[0].message.content or "Completed analysis."
                    break
                else:
                    raise e

            choice = response.choices[0]
            tool_calls = getattr(choice.message, "tool_calls", None)

            if not tool_calls:
                final_text = choice.message.content or ""
                break

            messages.append(choice.message)

            for call in tool_calls:
                fn_name = call.function.name
                try:
                    fn_args = json.loads(call.function.arguments or "{}")
                except Exception:
                    fn_args = {}

                # Execute through MCP
                tool_result = self._execute_tool(fn_name, fn_args)
                executed_tool_traces.append({
                    "name": fn_name,
                    "arguments": fn_args,
                    "result": tool_result,
                })

                if ("routing" in fn_name.lower() or "routes" in tool_result) and tool_result.get("ok"):
                    artifacts["routes"] = tool_result.get("routes", [])
                elif "env" in fn_name.lower() and tool_result.get("ok"):
                    artifacts["env_params"] = tool_result.get("data", {})

                # Compress payload to avoid 413 token limit
                compressed_content = self._compress_for_llm(fn_name, tool_result)

                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": fn_name,
                    "content": compressed_content,
                })

        # Strip any leaked XML tool tags
        final_text = re.sub(r"<tool_call>[\s\S]*?</tool_call>", "", final_text).strip()
        final_text = re.sub(r"<tool_call>[\s\S]*", "", final_text).strip()

        if not final_text and executed_tool_traces:
            last_trace = executed_tool_traces[-1]
            if last_trace.get("result", {}).get("ok"):
                final_text = f"Successfully executed `{last_trace['name']}`."
            else:
                final_text = f"Completed tool call with result: {last_trace.get('result', {}).get('error', 'Success')}."

        return {
            "response": final_text,
            "tool_calls": executed_tool_traces,
            "artifacts": artifacts,
            "model_used": f"{self.provider}:{self.model}",
        }
