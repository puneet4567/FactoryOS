
import asyncio
from typing import Literal
from unittest.mock import MagicMock, patch

# Mock environment variables BEFORE importing agent_graph
import os
os.environ["OLLAMA_HOST"] = "mock_host"
os.environ["DB_HOST"] = "mock_db"

# Mock classes to avoid real dependencies
with patch("langchain_ollama.ChatOllama") as MockOllama, \
     patch("psycopg2.connect"), \
     patch("langgraph.prebuilt.create_react_agent"):
    
    # Setup Mock LLM response behavior
    mock_llm_instance = MockOllama.return_value
    
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

        # Case 4: Finish
        mock_llm_instance.invoke.return_value.content = "FINISH"
        state = {"messages": [{"role": "user", "content": "Hello"}]}
        result = supervisor_node(state)
        assert result.goto == END
        print("✅ General Chat Routing: PASSED")

    if __name__ == "__main__":
        try:
            test_supervisor_routing()
            print("\n🎉 All Tests Passed!")
        except AssertionError as e:
            print(f"\n❌ Test Failed: {e}")
        except Exception as e:
            print(f"\n❌ Runtime Error: {e}")
