import json
import os
from typing import Dict, Any, List, Optional, Generator
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
            "microclimates, atmospheric parameters, and temperature-aware routing. "
            "You have access to FortyGuard's enterprise temperature tools via MCP. "
            "Follow these rules strictly:\n"
            "1. FortyGuard ONLY supports locations in the contiguous United States. Reject any coordinates outside the US.\n"
            "2. When users ask for route planning with thermal considerations, use the 'temperature_routing' tool.\n"
            "3. When users ask about environmental metrics, apparent temperature, wet-bulb temp, AQI, or solar irradiance, use 'env_params'.\n"
            "4. Provide thoughtful, accurate analysis of thermal stress, explaining difference between ambient temperature, heat index, and wet-bulb temperature.\n"
            "5. If a tool call is executed, summarize findings clearly with specific numbers and actionable takeaways."
        )

    def _get_mcp_tools_definitions(self) -> List[Dict[str, Any]]:
        """Convert FortyGuard MCP tool schemas into OpenAI/Groq function calling format."""
        tools = [
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
                    "description": "Get point-level environmental metrics: heat index, apparent temp, wet-bulb temp, relative humidity, AQI, and solar irradiance (GHI/DNI/DHI). Coordinates must be within contiguous US.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "latitude": {"type": "number", "description": "Decimal latitude (24.4 to 49.4)"},
                            "longitude": {"type": "number", "description": "Decimal longitude (-125.0 to -66.9)"},
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
                    "description": "Submit temperature-aware route generation between origin and destination coordinates in the US. Returns multiple routes (Fastest, Coolest, Balanced) with thermal exposure metrics.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "origin_lat": {"type": "number", "description": "Origin latitude"},
                            "origin_lon": {"type": "number", "description": "Origin longitude"},
                            "dest_lat": {"type": "number", "description": "Destination latitude"},
                            "dest_lon": {"type": "number", "description": "Destination longitude"},
                            "departure_time": {"type": "string", "description": "ISO-8601 departure timestamp (e.g. 2024-07-15T14:00:00Z)"},
                        },
                        "required": ["origin_lat", "origin_lon", "dest_lat", "dest_lon", "departure_time"],
                    },
                },
            },
        ]
        return tools

    def _execute_tool(self, name: str, args: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch tool calls to MCP client with safe handling."""
        if name == "credit_balance":
            return self.mcp.get_credit_balance()

        elif name == "env_params":
            return self.mcp.get_env_params(
                latitude=args["latitude"],
                longitude=args["longitude"],
                temperature=args["temperature"],
                date_str=args["date_str"],
                time_str=args.get("time_str", "12:00"),
            )

        elif name == "temperature_routing":
            origin = {"lat": args["origin_lat"], "lon": args["origin_lon"]}
            dest = {"lat": args["dest_lat"], "lon": args["dest_lon"]}
            return self.mcp.get_temperature_routing(
                origin=origin,
                destination=dest,
                departure_time=args["departure_time"],
            )

        return {"ok": False, "error": f"Unknown tool: {name}"}

    def chat(self, user_message: str, chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """
        Execute an agent turn with multi-step tool execution.
        Returns: {
            "response": str,
            "tool_calls": List[Dict],
            "artifacts": Dict (routes, env metrics, etc.),
            "model_used": str
        }
        """
        messages = [{"role": "system", "content": self.system_prompt}]
        if chat_history:
            messages.extend(chat_history)
        messages.append({"role": "user", "content": user_message})

        tools = self._get_mcp_tools_definitions()
        executed_tool_traces = []
        artifacts = {}

        # First LLM call
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools,
            tool_choice="auto",
            temperature=0.2,
        )

        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None)

        # If LLM requested tool calls
        if tool_calls:
            # Append assistant message with tool calls
            messages.append(choice.message)

            for call in tool_calls:
                fn_name = call.function.name
                fn_args = json.loads(call.function.arguments or "{}")

                # Execute through MCP
                tool_result = self._execute_tool(fn_name, fn_args)
                executed_tool_traces.append({
                    "name": fn_name,
                    "arguments": fn_args,
                    "result": tool_result,
                })

                if fn_name == "temperature_routing" and tool_result.get("ok"):
                    artifacts["routes"] = tool_result.get("routes", [])
                elif fn_name == "env_params" and tool_result.get("ok"):
                    artifacts["env_params"] = tool_result.get("data", {})

                # Append tool response
                messages.append({
                    "role": "tool",
                    "tool_call_id": call.id,
                    "name": fn_name,
                    "content": json.dumps(tool_result),
                })

            # Second LLM call for final synthesis
            final_response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0.3,
            )
            final_text = final_response.choices[0].message.content or "Completed analysis."
        else:
            final_text = choice.message.content or ""

        return {
            "response": final_text,
            "tool_calls": executed_tool_traces,
            "artifacts": artifacts,
            "model_used": f"{self.provider}:{self.model}",
        }
