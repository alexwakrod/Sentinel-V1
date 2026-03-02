import pyodbc
import logging
from datetime import datetime, timedelta, timezone
from config import DATABASE
logger = logging.getLogger(__name__)

def get_connection():
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

def init_crypto_tables():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='crypto_alerts' AND xtype='U')
            CREATE TABLE crypto_alerts (
                id INT IDENTITY(1,1) PRIMARY KEY,
                user_id BIGINT NOT NULL,
                coin_symbol NVARCHAR(20) NOT NULL,
                alert_price DECIMAL(20,8) NOT NULL,
                direction NVARCHAR(5) NOT NULL,
                duration_hours INT NOT NULL,
                dm_permission BIT DEFAULT 1,
                created_at DATETIME DEFAULT GETDATE(),
                expires_at DATETIME NOT NULL,
                triggered BIT DEFAULT 0,
                triggered_at DATETIME
            )
        """)
        conn.commit()

        cursor.execute("""
            IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='crypto_top_coins' AND xtype='U')
            CREATE TABLE crypto_top_coins (
                id INT IDENTITY(1,1) PRIMARY KEY,
                symbol NVARCHAR(20) NOT NULL,
                name NVARCHAR(100),
                updated_at DATETIME DEFAULT GETDATE()
            )
        """)
        conn.commit()
        logger.info("✅ Crypto tables initialised.")
    except pyodbc.Error as e:
        logger.error(f"Error creating crypto tables: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

# ---------- Alert CRUD ----------
def add_alert(user_id: int, coin: str, price: float, direction: str, duration_hours: int, dm_permission: bool) -> int:
    # Calculate expiration in Python (UTC)
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=duration_hours)
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO crypto_alerts (user_id, coin_symbol, alert_price, direction, duration_hours, dm_permission, expires_at)
            OUTPUT INSERTED.id
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, coin, price, direction, duration_hours, dm_permission, expires_at))
        row = cursor.fetchone()
        conn.commit()
        return row[0] if row else None
    except pyodbc.Error as e:
        logger.error(f"Failed to add alert: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()

def get_active_alerts():
    """Fetch all non‑triggered alerts; expiration will be checked in Python."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, user_id, coin_symbol, alert_price, direction, expires_at, dm_permission
            FROM crypto_alerts
            WHERE triggered = 0
        """)
        rows = cursor.fetchall()
        # Filter by expiration in Python (UTC)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        active = []
        for row in rows:
            expires_at = row.expires_at
            if expires_at.tzinfo is not None:
                expires_at = expires_at.replace(tzinfo=None)
            if expires_at > now:
                active.append(row)
        return active
    except pyodbc.Error as e:
        logger.error(f"Failed to fetch active alerts: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_user_alerts(user_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, coin_symbol, alert_price, direction, duration_hours, dm_permission,
                   created_at, expires_at, triggered, triggered_at
            FROM crypto_alerts
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        rows = cursor.fetchall()
        return rows
    except pyodbc.Error as e:
        logger.error(f"Failed to fetch user alerts: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_active_user_alerts(user_id: int):
    """Get non‑triggered alerts for a user, filtering expired by Python time."""
    from datetime import datetime, timezone
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, coin_symbol, alert_price, direction, expires_at
            FROM crypto_alerts
            WHERE user_id = ? AND triggered = 0
        """, (user_id,))
        rows = cursor.fetchall()
        now = datetime.now(timezone.utc)
        active = []
        for row in rows:
            expires_at = row.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at > now:
                active.append(row)
        return active
    except pyodbc.Error as e:
        logger.error(f"Failed to fetch user active alerts: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def mark_alert_triggered(alert_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE crypto_alerts
            SET triggered = 1, triggered_at = GETDATE()
            WHERE id = ?
        """, (alert_id,))
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to mark alert triggered: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def delete_alert(alert_id: int):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM crypto_alerts WHERE id = ?", (alert_id,))
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to delete alert: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

# ---------- Top coins cache ----------
def update_top_coins(coins: list):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM crypto_top_coins")
        for coin in coins:
            cursor.execute(
                "INSERT INTO crypto_top_coins (symbol, name) VALUES (?, ?)",
                (coin['symbol'], coin.get('name', coin['symbol']))
            )
        conn.commit()
    except pyodbc.Error as e:
        logger.error(f"Failed to update top coins: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def get_top_coins():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT symbol, name FROM crypto_top_coins ORDER BY id")
        rows = cursor.fetchall()
        return [{'symbol': row.symbol, 'name': row.name} for row in rows]
    except pyodbc.Error as e:
        logger.error(f"Failed to fetch top coins: {e}")
        return []
    finally:
        cursor.close()
        conn.close()