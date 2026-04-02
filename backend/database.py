import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "chat_history.db")

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        await db.execute("CREATE INDEX IF NOT EXISTS idx_session ON messages(session_id)")
        await db.commit()

async def save_message(session_id: str, role: str, content: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO messages (session_id, role, content, timestamp) VALUES (?, ?, ?, ?)",
            (session_id, role, content, datetime.utcnow().isoformat())
        )
        await db.commit()

async def get_history(session_id: str) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT role, content, timestamp FROM messages WHERE session_id=? ORDER BY id",
            (session_id,)
        ) as cur:
            rows = await cur.fetchall()
    return [{"role": r["role"], "content": r["content"], "timestamp": r["timestamp"]} for r in rows]

async def clear_session(session_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM messages WHERE session_id=?", (session_id,))
        await db.commit()

async def list_sessions() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT session_id,
                   MIN(content) as first_msg,
                   MAX(timestamp) as last_ts,
                   COUNT(*) as msg_count
            FROM messages WHERE role='user'
            GROUP BY session_id
            ORDER BY last_ts DESC
            LIMIT 20
        """) as cur:
            rows = await cur.fetchall()
    return [{"session_id": r["session_id"], "title": r["first_msg"][:48], "last_ts": r["last_ts"], "msg_count": r["msg_count"]} for r in rows]
