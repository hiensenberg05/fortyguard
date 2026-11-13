import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent
ENV_PATH = BASE_DIR / ".env"

# Load environment variables
load_dotenv(dotenv_path=ENV_PATH)

# FortyGuard Configurations
FORTY_GUARD_API_KEY = os.getenv("FORTY_GUARD_API_KEY", "").strip()
FORTY_GUARD_MCP_URL = "https://tos-mcp.app.fortyguard.com/mcp"
FORTY_GUARD_REST_BASE = "https://api.fortyguard.com/v1"

# LLM Configurations
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
GROK_API_KEY = os.getenv("GROK_API_KEY", os.getenv("XAI_API_KEY", "")).strip()

# Default Models
DEFAULT_GROQ_MODEL = "qwen/qwen3.8-27b"
DEFAULT_GROK_MODEL = "grok-2-latest"

# Credit costs table (as documented & empirical)
TOOL_CREDIT_COSTS = {
    "credit_balance": 0,
    "env_params": 2900,
    "temperature_routing": 3500,
    "temperature_routing_read": 0,
    "heatmap": 4220,
    "heatmap_read": 0,
    "report": 8600,
    "report_read": 0,
    "streetview": 8600,
    "satellite": 14400,
    "monitoring": 3500,
}

# Supported US Geographic Bounds (Contiguous US Bounding Box approx)
US_BOUNDS = {
    "min_lat": 24.396308,
    "max_lat": 49.384358,
    "min_lon": -125.0,
    "max_lon": -66.93457,
}

def is_within_us_bounds(lat: float, lon: float) -> bool:
    """Validate whether coordinate lies within contiguous United States bounding box."""
    return (
        US_BOUNDS["min_lat"] <= lat <= US_BOUNDS["max_lat"]
        and US_BOUNDS["min_lon"] <= lon <= US_BOUNDS["max_lon"]
    )
