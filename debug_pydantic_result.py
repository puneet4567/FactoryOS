
import asyncio
import os
from pydantic_ai import Agent

# Mock Env
os.environ["OLLAMA_BASE_URL"] = "http://localhost:11434/v1"

agent = Agent('ollama:llama3.2')

async def main():
    # We rely on the fact that we can't actually hit the LLM without it running,
    # but maybe we can mock the model to return a static string
    # forcing the agent to return a result object.
    
    # from pydantic_ai.result import RunResult
    # print("RunResult attributes:", dir(RunResult))
    
    # Or try to run with a mocked model
    from pydantic_ai.models.test import TestModel
    agent_test = Agent(TestModel())
    
    result = await agent_test.run("Hello")
    print("\n--- Result Object Inspection ---")
    print(f"Type: {type(result)}")
    print(f"Dir: {dir(result)}")
    try:
        print(f"Data: {result.data}")
    except AttributeError:
        print("No .data attribute")
        
    try:
        print(f"Output: {result.output}")
    except AttributeError:
        print("No .output attribute")

if __name__ == "__main__":
    asyncio.run(main())
