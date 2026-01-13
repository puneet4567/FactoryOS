import os
import psycopg2
from mcp.server.fastmcp import FastMCP
from psycopg2.extras import RealDictCursor

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
    """Answer questions by executing a READ-ONLY SQL query."""
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

if __name__ == "__main__":
    mcp.run()