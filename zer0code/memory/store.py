import aiosqlite
import os
import time


class MemoryStore:
    def __init__(self, db_path: str = "~/.zer0code/memory.db"):
        self.db_path = os.path.expanduser(db_path)
        self._db = None

    async def init(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._db = await aiosqlite.connect(self.db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript("""
            CREATE TABLE IF NOT EXISTS mistakes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                context TEXT NOT NULL,
                error TEXT NOT NULL,
                lesson TEXT NOT NULL,
                category TEXT NOT NULL,
                relevance_score REAL DEFAULT 1.0
            );
            CREATE TABLE IF NOT EXISTS successes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                context TEXT NOT NULL,
                approach TEXT NOT NULL,
                outcome TEXT NOT NULL,
                category TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tool_patterns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                pattern TEXT NOT NULL,
                anti_pattern TEXT NOT NULL,
                frequency INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                value TEXT NOT NULL,
                source TEXT NOT NULL,
                timestamp REAL NOT NULL,
                category TEXT NOT NULL
            );
        """)
        await self._db.commit()

    async def add_mistake(self, context: str, error: str, lesson: str, category: str):
        await self._db.execute(
            "INSERT INTO mistakes (timestamp, context, error, lesson, category) VALUES (?, ?, ?, ?, ?)",
            (time.time(), context, error, lesson, category),
        )
        await self._db.commit()

    async def add_success(self, context: str, approach: str, outcome: str, category: str):
        await self._db.execute(
            "INSERT INTO successes (timestamp, context, approach, outcome, category) VALUES (?, ?, ?, ?, ?)",
            (time.time(), context, approach, outcome, category),
        )
        await self._db.commit()

    async def add_tool_pattern(self, tool_name: str, pattern: str, anti_pattern: str):
        async with self._db.execute(
            "SELECT id, frequency FROM tool_patterns WHERE tool_name = ? AND pattern = ? AND anti_pattern = ?",
            (tool_name, pattern, anti_pattern),
        ) as cursor:
            row = await cursor.fetchone()
        if row:
            await self._db.execute(
                "UPDATE tool_patterns SET frequency = ? WHERE id = ?",
                (row["frequency"] + 1, row["id"]),
            )
        else:
            await self._db.execute(
                "INSERT INTO tool_patterns (tool_name, pattern, anti_pattern) VALUES (?, ?, ?)",
                (tool_name, pattern, anti_pattern),
            )
        await self._db.commit()

    async def add_knowledge(self, key: str, value: str, source: str, category: str):
        await self._db.execute(
            "INSERT INTO knowledge (key, value, source, timestamp, category) VALUES (?, ?, ?, ?, ?)",
            (key, value, source, time.time(), category),
        )
        await self._db.commit()

    async def get_relevant_mistakes(self, context: str, limit: int = 5) -> list:
        keywords = [w.lower() for w in context.split() if len(w) > 3]
        if not keywords:
            return []
        conditions = " OR ".join(["LOWER(context) LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        params.append(limit)
        async with self._db.execute(
            f"SELECT * FROM mistakes WHERE {conditions} ORDER BY relevance_score DESC, timestamp DESC LIMIT ?",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_relevant_successes(self, context: str, limit: int = 5) -> list:
        keywords = [w.lower() for w in context.split() if len(w) > 3]
        if not keywords:
            return []
        conditions = " OR ".join(["LOWER(context) LIKE ?" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        params.append(limit)
        async with self._db.execute(
            f"SELECT * FROM successes WHERE {conditions} ORDER BY timestamp DESC LIMIT ?",
            params,
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_tool_patterns(self, tool_name: str) -> list:
        async with self._db.execute(
            "SELECT * FROM tool_patterns WHERE tool_name = ? ORDER BY frequency DESC",
            (tool_name,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_knowledge(self, category: str = None) -> list:
        if category:
            async with self._db.execute(
                "SELECT * FROM knowledge WHERE category = ? ORDER BY timestamp DESC",
                (category,),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with self._db.execute(
                "SELECT * FROM knowledge ORDER BY timestamp DESC"
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_all_memories(self, limit: int = 50) -> dict:
        result = {}
        for table in ("mistakes", "successes", "tool_patterns", "knowledge"):
            async with self._db.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
            result[table] = [dict(row) for row in rows]
        return result

    async def get_stats(self) -> dict:
        stats = {}
        for table in ("mistakes", "successes", "tool_patterns", "knowledge"):
            async with self._db.execute(f"SELECT COUNT(*) as cnt FROM {table}") as cursor:
                row = await cursor.fetchone()
            stats[table] = row["cnt"]
        return stats

    async def clear(self):
        for table in ("mistakes", "successes", "tool_patterns", "knowledge"):
            await self._db.execute(f"DELETE FROM {table}")
        await self._db.commit()
