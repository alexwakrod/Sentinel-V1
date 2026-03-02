import pyodbc
import logging
from config import DATABASE

logger = logging.getLogger(__name__)

def get_connection():
    """Create and return a connection to SQL Server using SQL Server Authentication."""
    try:
        conn = pyodbc.connect(
            driver=DATABASE['driver'],
            server=DATABASE['server'],
            database=DATABASE['database'],
            uid=DATABASE['uid'],
            pwd=DATABASE['pwd'],
            autocommit=False
        )
        return conn
    except pyodbc.Error as e:
        logger.error(f"Database connection failed: {e}")
        raise

def init_db():
    """Create any tables that this bot might need in the future."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # ----- Example table for future use (e.g., tracking something) -----
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='handshake_events' AND xtype='U')
            CREATE TABLE handshake_events (
                id INT IDENTITY(1,1) PRIMARY KEY,
                event_type NVARCHAR(50) NOT NULL,
                license_code NVARCHAR(50) NOT NULL,
                details NVARCHAR(MAX),
                created_at DATETIME DEFAULT GETDATE()
            )
        """)
        conn.commit()
        logger.info("✅ HandshakeBot database tables initialised.")
    except pyodbc.Error as e:
        logger.error(f"Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# ---------- Example logging function ----------
def log_event(event_type: str, license_code: str, details: str = None):
    """Insert an event into the handshake_events table."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO handshake_events (event_type, license_code, details) VALUES (?, ?, ?)",
            (event_type, license_code, details)
        )
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to log event: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()