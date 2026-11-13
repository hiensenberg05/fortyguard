import unittest
from config import is_within_us_bounds
from fortyguard_mcp import FortyGuardMCPClient
from rest_client import FortyGuardRESTClient
from llm_agent import ThermalAgent

class TestFortyGuardAPIAndAgent(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.mcp = FortyGuardMCPClient()
        cls.rest = FortyGuardRESTClient()
        cls.agent = ThermalAgent(provider="groq", mcp_client=cls.mcp)

    def test_01_bounding_box_logic(self):
        """Test geographic bounds validator for contiguous US."""
        # Phoenix, AZ (In US)
        self.assertTrue(is_within_us_bounds(33.4484, -112.0740))
        # New York, NY (In US)
        self.assertTrue(is_within_us_bounds(40.7128, -74.0060))
        # Dubai, UAE (Outside US)
        self.assertFalse(is_within_us_bounds(25.2048, 55.2708))
        # London, UK (Outside US)
        self.assertFalse(is_within_us_bounds(51.5074, -0.1278))

    def test_02_rest_usage_endpoint(self):
        """Test REST API usage and plan retrieval."""
        res = self.rest.fetch_api_key_usage()
        self.assertEqual(res.get("status_code"), 200)
        data = res.get("data", {})
        self.assertIn("plan_details", data)
        self.assertIn("credit_summary", data)

    def test_03_mcp_handshake_and_tools(self):
        """Test MCP protocol initialization and tool discovery."""
        self.mcp.initialize()
        tools = self.mcp.list_tools(force_refresh=True)
        self.assertGreaterEqual(len(tools), 10)
        names = [t.get("name") for t in tools]
        self.assertIn("temperature_routing", names)
        self.assertIn("env_params", names)
        self.assertIn("credit_balance", names)

    def test_04_mcp_credit_balance(self):
        """Test MCP credit balance tool call (free)."""
        bal = self.mcp.get_credit_balance()
        self.assertTrue(bal.get("ok"))
        self.assertGreater(bal.get("available_credits", 0), 0)

    def test_05_out_of_bounds_rejection(self):
        """Test that international coordinates are rejected cleanly."""
        res = self.mcp.get_env_params(
            latitude=25.2048,
            longitude=55.2708,
            temperature=35.0,
            date_str="2024-07-15"
        )
        self.assertFalse(res.get("ok"))
        self.assertIn("outside", res.get("error", "").lower())

    def test_06_env_params_us_point(self):
        """Test point environmental parameters in Phoenix, AZ."""
        res = self.mcp.get_env_params(
            latitude=33.4484,
            longitude=-112.0740,
            temperature=38.0,
            date_str="2024-07-15",
            time_str="14:00"
        )
        self.assertTrue(res.get("ok"))
        data = res.get("data", {})
        self.assertIsNotNone(data)

    def test_07_agent_tool_calling(self):
        """Test LLM agent invoking MCP tools autonomously."""
        ans = self.agent.chat("How many credits do I have left?")
        self.assertIsNotNone(ans.get("response"))
        self.assertGreaterEqual(len(ans.get("tool_calls", [])), 1)
        self.assertEqual(ans["tool_calls"][0]["name"], "credit_balance")

if __name__ == "__main__":
    unittest.main(verbosity=2)
