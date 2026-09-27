import aiosqlite
import json
import os
import time
import uuid
from dataclasses import dataclass
from typing import Optional


@dataclass
class SessionInfo:
    session_id: str
    created_at: float
    updated_at: float
    title: str
    message_count: int
    provider: str
    model: str


class SessionManager:
    def __init__(self, db_path: str = "~/.truthzero/sessions.db"):
        self.db_path = os.path.expanduser(db_path)
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                title TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                metadata TEXT DEFAULT '{}'
            );
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                tool_calls TEXT,
                tool_call_id TEXT,
                name TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
            );
        """)
        await self._db.commit()

    async def create_session(self, provider: str, model: str, title: str = "") -> str:
        session_id = str(uuid.uuid4())[:8]
        now = time.time()
        if not title:
            title = f"Session {session_id}"
        await self._db.execute(
            "INSERT INTO sessions (session_id, created_at, updated_at, title, provider, model) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, now, now, title, provider, model),
        )
        await self._db.commit()
        return session_id

    async def save_message(self, session_id: str, message: dict):
        await self._db.execute(
            "INSERT INTO messages (session_id, timestamp, role, content, tool_calls, tool_call_id, name) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                session_id,
                time.time(),
                message.get("role", ""),
                message.get("content", "") if isinstance(message.get("content"), str) else json.dumps(message.get("content", "")),
                json.dumps(message.get("tool_calls")) if message.get("tool_calls") else None,
                message.get("tool_call_id"),
                message.get("name"),
            ),
        )
        await self._db.execute(
            "UPDATE sessions SET updated_at = ? WHERE session_id = ?",
            (time.time(), session_id),
        )
        await self._db.commit()

    async def load_session(self, session_id: str) -> list[dict]:
        async with self._db.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY id",
            (session_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        messages = []
        for row in rows:
            msg = {"role": row["role"], "content": row["content"]}
            if row["tool_calls"]:
                msg["tool_calls"] = json.loads(row["tool_calls"])
            if row["tool_call_id"]:
                msg["tool_call_id"] = row["tool_call_id"]
            if row["name"]:
                msg["name"] = row["name"]
            messages.append(msg)
        return messages

    async def list_sessions(self, limit: int = 20) -> list[SessionInfo]:
        async with self._db.execute(
            "SELECT s.*, COUNT(m.id) as msg_count FROM sessions s LEFT JOIN messages m ON s.session_id = m.session_id GROUP BY s.session_id ORDER BY s.updated_at DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [
            SessionInfo(
                session_id=row["session_id"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                title=row["title"],
                message_count=row["msg_count"],
                provider=row["provider"],
                model=row["model"],
            )
            for row in rows
        ]

    async def update_title(self, session_id: str, title: str):
        await self._db.execute(
            "UPDATE sessions SET title = ? WHERE session_id = ?",
            (title, session_id),
        )
        await self._db.commit()

    async def delete_session(self, session_id: str):
        await self._db.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        await self._db.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
        await self._db.commit()

    async def close(self):
        if self._db:
            await self._db.close()
