import os
import psycopg2
from mcp.server.fastmcp import FastMCP
from psycopg2.extras import RealDictCursor
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings

# Get DB Host from Docker Env
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5435")
DB_USER = os.getenv("POSTGRES_USER", "postgres")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "password")
DB_NAME = os.getenv("POSTGRES_DB", "krafix_factory")

DB_DSN = f"dbname={DB_NAME} user={DB_USER} password={DB_PASS} host={DB_HOST} port={DB_PORT}"

mcp = FastMCP("Krafix-Hybrid-Brain")

@mcp.tool()
def log_production(machine_id: str, rolls: int) -> str:
    """Log production output. Use only when user says 'log', 'record', or 'save'."""
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            # Create table if not exists (Auto-setup)
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

@mcp.tool()
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
            # Check exist
            cur.execute("SELECT id FROM inventory WHERE product_name ILIKE %s", (f"%{product_name}%",))
            if not cur.fetchone():
                # Auto-create item if missing
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

@mcp.tool()
def analyze_data(question_as_sql_query: str) -> str:
    """Execute a SQL query on 'production_logs' or 'inventory' tables ONLY. Do NOT use for troubleshooting or manuals."""
    forbidden = ["insert", "update", "delete", "drop", "truncate", "alter"]
    if any(word in question_as_sql_query.lower() for word in forbidden):
        return "❌ SAFETY ALERT: Read-only tool."

    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(question_as_sql_query)
            results = cur.fetchall()
            return str(results) if results else "0 results found."
    except Exception as e:
        return f"❌ SQL Error: {e}"
    finally:
        conn.close()

@mcp.tool()
def consult_manual(query: str) -> str:
    """Use this to find solutions for error codes (e.g. 'Error 502'), fix machines, or look up procedures in the manual."""
    try:
        OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_HOST)
        
        # Connect to existing DB
        db = Chroma(persist_directory="./chroma_db", embedding_function=embeddings)
        
        # Search
        results = db.similarity_search(query, k=3)
        if not results:
            return "No relevant info found in manuals."
        
        return "\n\n".join([r.page_content for r in results])
    except Exception as e:
        return f"❌ Error searching manual: {e}"

if __name__ == "__main__":
    mcp.run()