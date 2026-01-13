
import os
import psycopg2
from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings
from typing import Optional

# --- Configuration ---
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5435")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_NAME = os.getenv("POSTGRES_DB", "krafix_factory")
DB_DSN = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}"
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# PydanticAI uses OpenAI client -> Needs /v1 suffix for Ollama
os.environ["OLLAMA_BASE_URL"] = f"{OLLAMA_HOST}/v1"

# --- Dependencies ---
class AgentDeps:
    db_dsn: str = DB_DSN
    ollama_host: str = OLLAMA_HOST

# --- Agents ---

# 1. Production Agent
production_agent = Agent(
    'ollama:llama3.2',
    deps_type=AgentDeps,
    retries=3,
    system_prompt="You are a Production Logger. Your ONLY job is to log production data to the database using the provided tools. If successful, confirm the ID."
)

@production_agent.tool
async def log_production(ctx: RunContext[AgentDeps], machine_id: str, rolls: int) -> str:
    """Log production output. Use when user says 'log', 'record', or 'save'."""
    conn = psycopg2.connect(ctx.deps.db_dsn)
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

# 2. Inventory Agent
inventory_agent = Agent(
    'ollama:llama3.2',
    deps_type=AgentDeps,
    retries=3,
    system_prompt="You are an Inventory Manager. Update stock levels using the database tool."
)

@inventory_agent.tool
async def update_stock(ctx: RunContext[AgentDeps], product_name: str, quantity_change: int) -> str:
    """Update inventory. Positive int to ADD, Negative to REMOVE."""
    conn = psycopg2.connect(ctx.deps.db_dsn)
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

# 3. Maintenance Agent (RAG)
maintenance_agent = Agent(
    'ollama:llama3.2',
    deps_type=AgentDeps,
    retries=3,
    system_prompt="You are a Maintenance Expert. Consult the manual to solve errors."
)

@maintenance_agent.tool
async def consult_manual(ctx: RunContext[AgentDeps], query: str) -> str:
    """Use this to find solutions for error codes (e.g. 'Error 502') or look up procedures."""
    try:
        embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=ctx.deps.ollama_host)
        # Assuming RAG db exists
        db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        results = db.similarity_search(query, k=3)
        if not results:
            return "No relevant info found in manuals."
        return "\n\n".join([r.page_content for r in results])
    except Exception as e:
        return f"❌ Error searching manual: {e}"
