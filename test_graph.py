
import asyncio
from typing import Literal
from unittest.mock import MagicMock, patch
import os

# Mock environment variables BEFORE importing agent_graph
os.environ["OLLAMA_HOST"] = "mock_host"
os.environ["DB_HOST"] = "mock_db"

# Mock classes to avoid real dependencies
with patch("langchain_ollama.ChatOllama") as MockOllama, \
     patch("psycopg2.connect"), \
     patch("langgraph.prebuilt.create_react_agent"), \
     patch("agent_graph.production_agent") as mock_prod, \
     patch("agent_graph.inventory_agent") as mock_inv, \
     patch("agent_graph.maintenance_agent") as mock_maint:
    
    # Setup Mock LLM response behavior
    mock_llm_instance = MockOllama.return_value
    
    # Configure mocks to return an object with .output attribute (matching PydanticAI)
    mock_result = MagicMock()
    mock_result.output = "Mock Agent Output"
    
    mock_prod.run.return_value = mock_result
    mock_inv.run.return_value = mock_result
    mock_maint.run.return_value = mock_result
    
    from agent_graph import supervisor_node
    from langgraph.graph import MessagesState
    from langgraph.types import Command
    from langgraph.graph import END

    def test_supervisor_routing():
        print("🧪 Testing Supervisor Routing...")

        # Case 1: Production
        mock_llm_instance.invoke.return_value.content = "production_agent"
        state = {"messages": [{"role": "user", "content": "Log 50 rolls"}]}
        result = supervisor_node(state)
        assert isinstance(result, Command)
        assert result.goto == "production_agent"
        print("✅ Production Routing: PASSED")

        # Case 2: Inventory
        mock_llm_instance.invoke.return_value.content = "inventory_agent"
        state = {"messages": [{"role": "user", "content": "Update stock"}]}
        result = supervisor_node(state)
        assert result.goto == "inventory_agent"
        print("✅ Inventory Routing: PASSED")

        # Case 3: Maintenance
        mock_llm_instance.invoke.return_value.content = "maintenance_agent"
        state = {"messages": [{"role": "user", "content": "Error 502"}]}
        result = supervisor_node(state)
        assert result.goto == "maintenance_agent"
        print("✅ Maintenance Routing: PASSED")

        # Case 4: General Chat (fallback)
        mock_llm_instance.invoke.return_value.content = "How are you?"
        # The logic: if not in list, fallback to message + END
        state = {"messages": [{"role": "user", "content": "Hello"}]}
        result = supervisor_node(state)
        
        # Verify it goes to END
        assert result.goto == END
        # Verify it provides an update (the response)
        assert "messages" in result.update
        print("✅ General Chat Routing: PASSED")

    if __name__ == "__main__":
        try:
            test_supervisor_routing()
            print("\n🎉 All Tests Passed!")
        except AssertionError as e:
            print(f"\n❌ Test Failed: {e}")
        except Exception as e:
            print(f"\n❌ Runtime Error: {e}")
