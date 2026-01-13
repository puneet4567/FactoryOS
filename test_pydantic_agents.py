
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import os

# Set Env Vars for Testing
os.environ["OLLAMA_HOST"] = "http://mock-ollama:11434"
os.environ["DB_HOST"] = "mock-db"

# Mock PydanticAI to avoid real network calls during import if possible,
# BUT we want to test the configuration logic in pydantic_agent.py
# So we will let it import but mock the underlying providers if needed.

# We need to mock OllamaProvider because pydantic_agent instantiates it at import time (via Agent)
# and it checks for OLLAMA_BASE_URL.

class TestPydanticAgents(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        # Ensure OLLAMA_BASE_URL is set as expected by the module
        # The module sets it on import, but we want to verify that logic.
        if "OLLAMA_BASE_URL" in os.environ:
            del os.environ["OLLAMA_BASE_URL"]

    async def test_agent_configuration(self):
        """Verify that OLLAMA_BASE_URL is correctly set with /v1 suffix"""
        import pydantic_agent
        import importlib
        importlib.reload(pydantic_agent)
        
        # Check if the module correctly added /v1
        expected_url = "http://mock-ollama:11434/v1"
        self.assertEqual(os.environ["OLLAMA_BASE_URL"], expected_url)
        print("\n✅ Configuration Test: OLLAMA_BASE_URL set correctly.")

    @patch("psycopg2.connect")
    async def test_production_agent_tool(self, mock_connect):
        """Test log_production tool logic"""
        from pydantic_agent import log_production, AgentDeps
        
        # Setup Mock DB
        mock_conn = mock_connect.return_value
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        mock_cur.fetchone.return_value = [123] # Mock ID return

        deps = AgentDeps()
        ctx = MagicMock()
        ctx.deps = deps

        result = await log_production(ctx, "Machine-X", 50)
        
        # Verify SQL
        self.assertIn("INSERT INTO production_logs", mock_cur.execute.call_args_list[1][0][0])
        self.assertIn("✅ Success. Logged to Database. ID: 123", result)
        print("✅ Production Tool Test: SQL execution verified.")

    @patch("psycopg2.connect")
    async def test_inventory_agent_tool(self, mock_connect):
        """Test update_stock tool logic"""
        from pydantic_agent import update_stock, AgentDeps
        
        mock_conn = mock_connect.return_value
        mock_cur = mock_conn.cursor.return_value
        mock_cur.__enter__.return_value = mock_cur
        mock_cur.fetchone.side_effect = [None, [99]] # First None (check exist), then 99 (returning qty)

        deps = AgentDeps()
        ctx = MagicMock()
        ctx.deps = deps

        result = await update_stock(ctx, "Gears", 10)
        
        self.assertIn("INSERT INTO inventory", mock_cur.execute.call_args_list[2][0][0])
        self.assertIn("✅ Stock Updated. Gears: 99", result)
        print("✅ Inventory Tool Test: Logic verified.")

if __name__ == "__main__":
    unittest.main()
