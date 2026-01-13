import os
import psycopg2
from typing import TypedDict, Literal, Annotated
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import create_react_agent
from langgraph.types import Command

# --- Configuration ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5435")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_NAME = os.getenv("POSTGRES_DB", "krafix_factory")
DB_DSN = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")

# Tools are now imported from pydantic_agent.py


# --- Supervisor & Agents ---
from pydantic_agent import production_agent, inventory_agent, maintenance_agent, AgentDeps

# Create Deps object
deps = AgentDeps()

llm = ChatOllama(model="llama3.2", base_url=OLLAMA_HOST, temperature=0)

# Wrappers for PydanticAI Agents to work in LangGraph
async def call_production_agent(state: MessagesState):
    user_msg = state["messages"][-1].content
    result = await production_agent.run(user_msg, deps=deps)
    return {"messages": [{"role": "assistant", "content": result.output}]}

async def call_inventory_agent(state: MessagesState):
    user_msg = state["messages"][-1].content
    result = await inventory_agent.run(user_msg, deps=deps)
    return {"messages": [{"role": "assistant", "content": result.output}]}

async def call_maintenance_agent(state: MessagesState):
    user_msg = state["messages"][-1].content
    result = await maintenance_agent.run(user_msg, deps=deps)
    return {"messages": [{"role": "assistant", "content": result.output}]}

# Supervisor Node
def supervisor_node(state: MessagesState) -> Command[Literal["production_agent", "inventory_agent", "maintenance_agent", "__end__"]]:
    messages = [
        {"role": "system", "content": """You are a factory supervisor. Manage the conversation by routing to the correct worker.
        
        - If user wants to LOG output -> route to 'production_agent'.
        - If user wants to UPDATE STOCK -> route to 'inventory_agent'.
        - If user has an ERROR or needs MANUAL -> route to 'maintenance_agent'.
        - IF THE INTENT IS UNCLEAR OR GENERAL CHAT -> You MUST reply to the user yourself.
        
        PHONETIC CORRECTION:
        - "Law" -> "Log"
        - "Rules" / "Roles" / "Doles" -> "Rolls"
        - "Luxion" -> "Production"
        
        Return the name of the next agent specificly: 'production_agent', 'inventory_agent', 'maintenance_agent'.
        
        CRITICAL INSTRUCTION:
        If the last message in the history is a successful response from an agent (e.g. "Success", "Stock Updated", "Logged"), then you MUST route to 'FINISH'. Do NOT simply repeat the confirmation.
        ONLY route to 'FINISH' if the task is complete or the user said goodbye.
        """},
    ] + state["messages"]
    
    response = llm.invoke(messages)
    decision = response.content.strip().lower()

    if "production" in decision:
        return Command(goto="production_agent")
    elif "inventory" in decision:
        return Command(goto="inventory_agent")
    elif "maintenance" in decision:
        return Command(goto="maintenance_agent")
    else:
        # If the LLM says "FINISH" (even with extra text), it's a control signal -> End without adding a message.
        if "finish" in decision:
             return Command(goto=END)
        
        # Otherwise, if it's general chat (e.g. "Hello"), add it to the state.
        return Command(
            goto=END,
            update={"messages": [{"role": "assistant", "content": response.content}]}
        )

# Build Graph
builder = StateGraph(MessagesState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("production_agent", call_production_agent)
builder.add_node("inventory_agent", call_inventory_agent)
builder.add_node("maintenance_agent", call_maintenance_agent)

builder.add_edge(START, "supervisor")

# Workers return to supervisor to report back
builder.add_edge("production_agent", "supervisor")
builder.add_edge("inventory_agent", "supervisor")
builder.add_edge("maintenance_agent", "supervisor")

graph = builder.compile()
