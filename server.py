# server.py
import psycopg2
from mcp.server.fastmcp import FastMCP
from psycopg2.extras import RealDictCursor

# Initialize the Server
mcp = FastMCP("Krafix-Hybrid-Brain")

# DB Config (Ensure your Postgres is running)
DB_DSN = "dbname=krafix_factory user=postgres password=password"

# --- PART 1: THE "STRICT BUREAUCRAT" (Write Tools) ---

@mcp.tool()
def log_production(machine_id: str, rolls: int) -> str:
    """
    Log production output. 
    Use this ONLY when the user explicitly says to 'log', 'record', or 'save'.
    """
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO production_logs (machine_id, rolls_produced, timestamp) VALUES (%s, %s, NOW()) RETURNING id",
                (machine_id, rolls)
            )
            new_id = cur.fetchone()[0]
            conn.commit()
            return f"✅ Success. Logged to Database. ID: {new_id}"
    except Exception as e:
        return f"❌ Error logging production: {e}"
    finally:
        conn.close()

@mcp.tool()
def update_stock(product_name: str, quantity_change: int) -> str:
    """
    Update inventory count. 
    Positive integer to ADD stock, Negative to REMOVE stock.
    """
    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor() as cur:
            # Check if exists first
            cur.execute("SELECT id FROM inventory WHERE product_name ILIKE %s", (f"%{product_name}%",))
            if not cur.fetchone():
                return f"❌ Product '{product_name}' not found. Create it first."

            cur.execute(
                "UPDATE inventory SET quantity = quantity + %s WHERE product_name ILIKE %s RETURNING quantity",
                (quantity_change, f"%{product_name}%")
            )
            new_qty = cur.fetchone()[0]
            conn.commit()
            return f"✅ Stock Updated. New Balance for {product_name}: {new_qty}"
    except Exception as e:
        return f"❌ Error updating stock: {e}"
    finally:
        conn.close()

# --- PART 2: THE "CREATIVE GENIUS" (Read Tool) ---

DB_SCHEMA = """
Tables:
1. inventory (id, product_name, quantity, unit)
2. production_logs (id, machine_id, rolls_produced, timestamp)
"""

@mcp.tool()
def analyze_data(question_as_sql_query: str) -> str:
    """
    Answer questions by executing a READ-ONLY SQL query.
    Schema:
    {DB_SCHEMA}
    
    Rules:
    1. ONLY SELECT statements allowed.
    2. No INSERT, UPDATE, DELETE, DROP.
    """
    # Safety Check (The "Firewall")
    forbidden = ["insert", "update", "delete", "drop", "truncate", "alter"]
    if any(word in question_as_sql_query.lower() for word in forbidden):
        return "❌ SAFETY ALERT: This tool is for READING only. Use specific tools for modification."

    conn = psycopg2.connect(DB_DSN)
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(question_as_sql_query)
            results = cur.fetchall()
            if not results:
                return "0 results found."
            return str(results) # Return raw data, let LLM summarize it
    except Exception as e:
        return f"❌ SQL Error: {e}"
    finally:
        conn.close()

if __name__ == "__main__":
    mcp.run()