import os, requests, json
from dotenv import load_dotenv

load_dotenv()
api_key = os.getenv("FORTY_GUARD_API_KEY")

headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream"
}

tools_payload = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/list",
    "params": {}
}

r = requests.post("https://tos-mcp.app.fortyguard.com/mcp", headers=headers, json=tools_payload, timeout=15)
for line in r.text.splitlines():
    if line.startswith("data:"):
        data = json.loads(line[5:].strip())
        tools = data.get("result", {}).get("tools", [])
        print(f"Total tools discovered: {len(tools)}\n")
        for idx, t in enumerate(tools, 1):
            name = t.get("name")
            desc = t.get("description", "")
            params = t.get("inputSchema", {}).get("properties", {})
            required = t.get("inputSchema", {}).get("required", [])
            print(f"{idx}. Tool: {name}")
            print(f"   Description: {desc}")
            print(f"   Required parameters: {required}")
            print(f"   Parameter keys: {list(params.keys())}")
            print("-" * 50)
