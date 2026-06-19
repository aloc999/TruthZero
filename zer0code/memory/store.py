import aiosqlite
import json
import math
import os
import re
import time
from typing import Optional


STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "that", "this",
    "it", "its", "i", "me", "my", "we", "our", "you", "your", "he", "him",
    "his", "she", "her", "they", "them", "their", "what", "which", "who",
    "whom", "these", "those",
}


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
            CREATE TABLE IF NOT EXISTS episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                tool_name TEXT NOT NULL,
                args_json TEXT NOT NULL,
                result_summary TEXT NOT NULL,
                success INTEGER NOT NULL,
                context TEXT NOT NULL,
                duration_ms INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS strategies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                context_pattern TEXT NOT NULL,
                strategy TEXT NOT NULL,
                success_rate REAL DEFAULT 0.5,
                usage_count INTEGER DEFAULT 0,
                last_used REAL NOT NULL
            );
        """)
        await self._db.commit()

    def _tokenize(self, text: str) -> list[str]:
        tokens = re.split(r"[^a-zA-Z]+", text.lower())
        return [t for t in tokens if t and t not in STOPWORDS and len(t) > 1]

    def _compute_tfidf(self, query_tokens: list[str], doc_tokens_list: list[list[str]]) -> list[float]:
        if not doc_tokens_list or not query_tokens:
            return [0.0] * len(doc_tokens_list)

        num_docs = len(doc_tokens_list)
        df: dict[str, int] = {}
        for tokens in doc_tokens_list:
            seen = set(tokens)
            for token in seen:
                df[token] = df.get(token, 0) + 1

        scores = []
        for doc_tokens in doc_tokens_list:
            if not doc_tokens:
                scores.append(0.0)
                continue
            score = 0.0
            tf_map: dict[str, int] = {}
            for t in doc_tokens:
                tf_map[t] = tf_map.get(t, 0) + 1
            doc_len = len(doc_tokens)
            for qt in query_tokens:
                tf = tf_map.get(qt, 0) / doc_len
                idf = math.log((num_docs + 1) / (df.get(qt, 0) + 1)) + 1.0
                score += tf * idf
            scores.append(score)

        return scores

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
        query_tokens = self._tokenize(context)
        if not query_tokens:
            return []
        async with self._db.execute("SELECT * FROM mistakes") as cursor:
            rows = await cursor.fetchall()
        if not rows:
            return []
        rows = [dict(r) for r in rows]
        doc_tokens_list = [
            self._tokenize(f"{r['context']} {r['error']} {r['lesson']}") for r in rows
        ]
        tfidf_scores = self._compute_tfidf(query_tokens, doc_tokens_list)
        for i, row in enumerate(rows):
            row["_score"] = tfidf_scores[i] * row.get("relevance_score", 1.0)
        ranked = sorted(rows, key=lambda r: r["_score"], reverse=True)
        results = []
        for r in ranked[:limit]:
            if r["_score"] > 0:
                r.pop("_score", None)
                results.append(r)
        return results

    async def get_relevant_successes(self, context: str, limit: int = 5) -> list:
        query_tokens = self._tokenize(context)
        if not query_tokens:
            return []
        async with self._db.execute("SELECT * FROM successes") as cursor:
            rows = await cursor.fetchall()
        if not rows:
            return []
        rows = [dict(r) for r in rows]
        doc_tokens_list = [
            self._tokenize(f"{r['context']} {r['approach']} {r['outcome']}") for r in rows
        ]
        tfidf_scores = self._compute_tfidf(query_tokens, doc_tokens_list)
        for i, row in enumerate(rows):
            row["_score"] = tfidf_scores[i]
        ranked = sorted(rows, key=lambda r: r["_score"], reverse=True)
        results = []
        for r in ranked[:limit]:
            if r["_score"] > 0:
                r.pop("_score", None)
                results.append(r)
        return results

    async def apply_decay(self, half_life_days: float = 30.0):
        now = time.time()
        half_life_seconds = half_life_days * 86400.0
        decay_constant = math.log(2) / half_life_seconds
        async with self._db.execute(
            "SELECT id, timestamp, relevance_score FROM mistakes"
        ) as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            age = now - row["timestamp"]
            decay_factor = math.exp(-decay_constant * age)
            new_score = row["relevance_score"] * decay_factor
            await self._db.execute(
                "UPDATE mistakes SET relevance_score = ? WHERE id = ?",
                (new_score, row["id"]),
            )
        await self._db.commit()

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

    async def add_episode(
        self,
        session_id: str,
        tool_name: str,
        args: dict,
        result_summary: str,
        success: bool,
        context: str,
        duration_ms: int,
    ):
        args_json = json.dumps(args) if isinstance(args, dict) else str(args)
        await self._db.execute(
            "INSERT INTO episodes (session_id, timestamp, tool_name, args_json, result_summary, success, context, duration_ms) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, time.time(), tool_name, args_json, result_summary, int(success), context, duration_ms),
        )
        await self._db.commit()

    async def get_recent_episodes(self, session_id: str = None, limit: int = 20) -> list:
        if session_id:
            async with self._db.execute(
                "SELECT * FROM episodes WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
                (session_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with self._db.execute(
                "SELECT * FROM episodes ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def add_strategy(self, context_pattern: str, strategy: str):
        await self._db.execute(
            "INSERT INTO strategies (context_pattern, strategy, last_used) VALUES (?, ?, ?)",
            (context_pattern, strategy, time.time()),
        )
        await self._db.commit()

    async def update_strategy_outcome(self, strategy_id: int, success: bool):
        async with self._db.execute(
            "SELECT success_rate, usage_count FROM strategies WHERE id = ?",
            (strategy_id,),
        ) as cursor:
            row = await cursor.fetchone()
        if not row:
            return
        count = row["usage_count"] + 1
        old_rate = row["success_rate"]
        new_rate = old_rate + ((1.0 if success else 0.0) - old_rate) / count
        await self._db.execute(
            "UPDATE strategies SET success_rate = ?, usage_count = ?, last_used = ? WHERE id = ?",
            (new_rate, count, time.time(), strategy_id),
        )
        await self._db.commit()

    async def get_best_strategy(self, context: str) -> Optional[dict]:
        query_tokens = self._tokenize(context)
        if not query_tokens:
            return None
        async with self._db.execute(
            "SELECT * FROM strategies WHERE usage_count > 0 ORDER BY success_rate DESC"
        ) as cursor:
            rows = await cursor.fetchall()
        if not rows:
            return None
        rows = [dict(r) for r in rows]
        doc_tokens_list = [self._tokenize(r["context_pattern"]) for r in rows]
        scores = self._compute_tfidf(query_tokens, doc_tokens_list)
        best_idx = -1
        best_combined = -1.0
        for i, row in enumerate(rows):
            if scores[i] > 0:
                combined = scores[i] * row["success_rate"]
                if combined > best_combined:
                    best_combined = combined
                    best_idx = i
        if best_idx >= 0:
            return rows[best_idx]
        return None

    async def get_all_memories(self, limit: int = 50) -> dict:
        result = {}
        for table in ("mistakes", "successes", "tool_patterns", "knowledge", "episodes", "strategies"):
            async with self._db.execute(
                f"SELECT * FROM {table} ORDER BY id DESC LIMIT ?", (limit,)
            ) as cursor:
                rows = await cursor.fetchall()
            result[table] = [dict(row) for row in rows]
        return result

    async def get_stats(self) -> dict:
        stats = {}
        for table in ("mistakes", "successes", "tool_patterns", "knowledge", "episodes", "strategies"):
            async with self._db.execute(
                f"SELECT COUNT(*) as cnt FROM {table}"
            ) as cursor:
                row = await cursor.fetchone()
            stats[table] = row["cnt"]
        return stats

    async def get_recent_lessons(self, limit: int = 10) -> list[str]:
        async with self._db.execute(
            "SELECT lesson FROM mistakes ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [row["lesson"] for row in rows]

    async def add_reasoning_trace(self, session_id: str, user_input: str, reasoning: str, tools_used: list, outcome: str):
        await self._db.execute(
            "INSERT INTO knowledge (key, value, source, timestamp, category) VALUES (?, ?, ?, ?, ?)",
            (f"trace:{session_id}", json.dumps({"input": user_input[:200], "reasoning": reasoning[:500], "tools": tools_used, "outcome": outcome[:200]}), "reasoning_trace", time.time(), "reasoning"),
        )
        await self._db.commit()

    async def add_behavioral_pattern(self, pattern_type: str, description: str):
        existing = await self.get_knowledge(category="behavior")
        for e in existing:
            if e.get("key") == f"behavior:{pattern_type}" and description in e.get("value", ""):
                return
        await self._db.execute(
            "INSERT INTO knowledge (key, value, source, timestamp, category) VALUES (?, ?, ?, ?, ?)",
            (f"behavior:{pattern_type}", description, "self_analysis", time.time(), "behavior"),
        )
        await self._db.commit()

    async def consolidate_memories(self, max_age_days: int = 30):
        cutoff = time.time() - (max_age_days * 86400)
        lessons = {}
        async with self._db.execute("SELECT id, lesson, category FROM mistakes WHERE timestamp < ?", (cutoff,)) as cursor:
            rows = await cursor.fetchall()
        for row in rows:
            key = row["category"]
            if key not in lessons:
                lessons[key] = []
            lessons[key].append({"id": row["id"], "lesson": row["lesson"]})

        consolidated = 0
        for category, items in lessons.items():
            if len(items) < 3:
                continue
            merged = "; ".join(item["lesson"][:100] for item in items[:10])
            await self._db.execute(
                "INSERT INTO knowledge (key, value, source, timestamp, category) VALUES (?, ?, ?, ?, ?)",
                (f"consolidated:{category}", f"Merged {len(items)} lessons: {merged}", "consolidation", time.time(), "consolidated"),
            )
            ids = [item["id"] for item in items]
            placeholders = ",".join("?" * len(ids))
            await self._db.execute(f"DELETE FROM mistakes WHERE id IN ({placeholders})", ids)
            consolidated += len(items)

        await self._db.commit()
        return consolidated

    async def get_behavioral_patterns(self) -> list:
        return await self.get_knowledge(category="behavior")

    async def get_reasoning_traces(self, limit: int = 10) -> list:
        traces = await self.get_knowledge(category="reasoning")
        results = []
        for t in traces[:limit]:
            try:
                data = json.loads(t.get("value", "{}"))
                results.append(data)
            except Exception:
                pass
        return results

    async def clear(self):
        for table in ("mistakes", "successes", "tool_patterns", "knowledge", "episodes", "strategies"):
            await self._db.execute(f"DELETE FROM {table}")
        await self._db.commit()
