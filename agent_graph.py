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

# --- Tools (Ported from server.py) ---

@tool
def log_production(machine_id: str, rolls: int) -> str:
    """Log production output. Use when user says 'log', 'record', or 'save'."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS production_logs (
                    id SERIAL PRIMARY KEY, machine_id TEXT, rolls_produced INT, timestamp TIMESTAMP DEFAULT NOW()
                );
            """)
            cur.execute(
                "INSERT INTO production_logs (machine_id, rolls_produced) VALUES (%s, %s) RETURNING id",
                (machine_id, rolls)
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return f"✅ Success. Logged to Database. ID: {new_id}"
    except Exception as e:
        return f"❌ Error logging: {e}"
    finally:
        conn.close()

@tool
def update_stock(product_name: str, quantity_change: int) -> str:
    """Update inventory. Positive int to ADD, Negative to REMOVE."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS inventory (
                    id SERIAL PRIMARY KEY, product_name TEXT UNIQUE, quantity INT DEFAULT 0
                );
            """)
            cur.execute("SELECT id FROM inventory WHERE product_name ILIKE %s", (f"%{product_name}%",))
            if not cur.fetchone():
                cur.execute("INSERT INTO inventory (product_name, quantity) VALUES (%s, 0)", (product_name,))
            
            cur.execute(
                "UPDATE inventory SET quantity = quantity + %s WHERE product_name ILIKE %s RETURNING quantity",
                (quantity_change, f"%{product_name}%")
            )
            new_qty = cur.fetchone()[0]
            conn.commit()
            return f"✅ Stock Updated. {product_name}: {new_qty}"
    except Exception as e:
        return f"❌ Error updating stock: {e}"
    finally:
        conn.close()

@tool
def consult_manual(query: str) -> str:
    """Use this to find solutions for error codes (e.g. 'Error 502'), fix machines, or look up procedures in the manual."""
    try:
        embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST)
        db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        results = db.similarity_search(query, k=3)
        if not results:
            return "No relevant info found in manuals."
        return "\n\n".join([r.page_content for r in results])
    except Exception as e:
        return f"❌ Error searching manual: {e}"

# --- Supervisor & Agents ---

llm = ChatOllama(model="llama3.2", base_url=OLLAMA_HOST, temperature=0)

# Specialized Agents
production_agent = create_react_agent(llm, tools=[log_production])
inventory_agent = create_react_agent(llm, tools=[update_stock])
maintenance_agent = create_react_agent(llm, tools=[consult_manual])

# Supervisor Node
def supervisor_node(state: MessagesState) -> Command[Literal["production_agent", "inventory_agent", "maintenance_agent", "__end__"]]:
    messages = [
        {"role": "system", "content": """You are a factory supervisor. Manage the conversation by routing to the correct worker.
        
        - If user wants to LOG output -> route to 'production_agent'.
        - If user wants to UPDATE STOCK -> route to 'inventory_agent'.
        - If user has an ERROR or needs MANUAL -> route to 'maintenance_agent'.
        - If the previous tool output answers the question, or if it is general chat -> route to FINISH.
        
        Return the name of the next agent specificly: 'production_agent', 'inventory_agent', 'maintenance_agent', or 'FINISH'."""},
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
        return Command(goto=END)

# Build Graph
builder = StateGraph(MessagesState)

builder.add_node("supervisor", supervisor_node)
builder.add_node("production_agent", production_agent)
builder.add_node("inventory_agent", inventory_agent)
builder.add_node("maintenance_agent", maintenance_agent)

builder.add_edge(START, "supervisor")

# Workers return to supervisor to report back
builder.add_edge("production_agent", "supervisor")
builder.add_edge("inventory_agent", "supervisor")
builder.add_edge("maintenance_agent", "supervisor")

graph = builder.compile()
