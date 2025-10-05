import sqlite3, time, json
from .config import TELEMETRY_DB_PATH
from .utils import logger, safe_json

def get_conn():
    return sqlite3.connect(TELEMETRY_DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_hash_hex TEXT NOT NULL,
                telemetry_json TEXT NOT NULL,
                updated_at REAL
            )
        """)
    logger.info("Telemetry DB initialized.")

def serialize(data):
    return json.dumps(data, default=safe_json)

def save(source_hash, data):
    telemetry_json = serialize(data)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO telemetry (source_hash_hex, telemetry_json, updated_at) VALUES (?, ?, ?)",
            (source_hash, telemetry_json, time.time())
        )
    logger.info(f"Saved telemetry for {source_hash} ({len(telemetry_json)} bytes)")

def load_history(source_hash, limit=5):
    with get_conn() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("""
            SELECT telemetry_json, updated_at FROM telemetry
            WHERE source_hash_hex=? ORDER BY updated_at DESC LIMIT ?
        """, (source_hash, limit)).fetchall()

    history = []
    for r in rows:
        history.append({"updated_at": r["updated_at"], "data": json.loads(r["telemetry_json"])})
    return history
