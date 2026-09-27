"""Postgres-backed blackboard (beta) — transactional writes, decay in SQL.

Requires `psycopg[binary]` + a reachable Postgres 16 (+pgvector for
similarity search; plain SQL works without it). Fails open:
`connect()` returns False when unavailable and the caller keeps using
the memory board. Migration SQL ships here; the runner still defaults
to the memory board.

Embeddings: pluggable. Default is a dependency-free deterministic
hashing vectorizer (384-dim, L2-normalized) — good enough for
similar-recall. Swap in a real model (e.g. via Ollama/Together) by
passing `embed_fn`. The vector column + `<=>` search need the pgvector
extension; everything degrades gracefully without it.

DSN: $ZER0CODE_PG_DSN or postgresql://zer0code:zer0code@localhost:5432/zer0code
"""
from __future__ import annotations

import hashlib
import math
import os
import re
import time
from dataclasses import asdict
from typing import Callable

from zer0code.swarm.blackboard import Finding, FINDING_HALF_LIVES, DEFAULT_HALF_LIFE

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS swarm_findings (
    finding_id TEXT PRIMARY KEY,
    ftype TEXT NOT NULL DEFAULT 'NOTE',
    title TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'info',
    target TEXT NOT NULL DEFAULT '',
    evidence TEXT NOT NULL DEFAULT '',
    agent TEXT NOT NULL DEFAULT '',
    created_at DOUBLE PRECISION NOT NULL,
    weight DOUBLE PRECISION NOT NULL DEFAULT 1.0
);
CREATE INDEX IF NOT EXISTS idx_swarm_findings_type ON swarm_findings (ftype);
CREATE INDEX IF NOT EXISTS idx_swarm_findings_target ON swarm_findings (target);
"""

VECTOR_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;
ALTER TABLE swarm_findings ADD COLUMN IF NOT EXISTS embedding vector({dim});
"""

_TOKEN_RE = re.compile(r"[a-z0-9]{2,}")


def hashing_embed(text: str, dim: int = 384) -> list[float]:
    """Deterministic zero-dependency embedding (hashing trick, L2-normed).

    Stable across runs (hashlib, never hash()). Similar texts share
    buckets, so cosine recall works for near-duplicates. NOT a semantic
    model — replace with a real one for production similarity.
    """
    vec = [0.0] * dim
    for tok in _TOKEN_RE.findall((text or "").lower()):
        idx = int(hashlib.sha256(tok.encode()).hexdigest(), 16) % dim
        vec[idx] += 1.0
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]

# Pheromone decay in SQL: weight * 0.5 ^ (age / half_life).
# Half-lives passed as a CASE expression built from FINDING_HALF_LIVES.
def _half_life_case() -> str:
    whens = " ".join(
        f"WHEN '{k}' THEN {float(v)}" for k, v in FINDING_HALF_LIVES.items())
    return f"CASE ftype {whens} ELSE {float(DEFAULT_HALF_LIFE)} END"


def dsn_from_env() -> str:
    return os.environ.get(
        "ZER0CODE_PG_DSN",
        "postgresql://zer0code:zer0code@localhost:5432/zer0code")


class PostgresBoard:
    """Thin Postgres mirror of Blackboard. Not a full replacement (beta)."""

    def __init__(self, dsn: str = "", dim: int = 384,
                 embed_fn: Callable[[str], list[float]] | None = None):
        self.dsn = dsn or dsn_from_env()
        self._conn = None
        self.error = ""
        self.dim = dim
        self._embed = embed_fn or (lambda text: hashing_embed(text, dim))
        self._vector_ready = False

    def connect(self) -> bool:
        try:
            import psycopg
            self._conn = psycopg.connect(self.dsn, connect_timeout=5)
            with self._conn.cursor() as cur:
                cur.execute(SCHEMA_SQL)
            self._conn.commit()
            return True
        except Exception as e:
            self.error = str(e)[:300]
            self._conn = None
            return False

    def close(self) -> None:
        try:
            if self._conn:
                self._conn.close()
        except Exception:
            pass
        self._conn = None

    def write(self, finding: Finding) -> str:
        if not self._conn:
            raise ConnectionError("PostgresBoard not connected")
        d = asdict(finding)
        with self._conn.cursor() as cur:
            cur.execute(
                """INSERT INTO swarm_findings
                   (finding_id, ftype, title, detail, severity, target,
                    evidence, agent, created_at, weight)
                   VALUES (%(finding_id)s, %(ftype)s, %(title)s, %(detail)s,
                           %(severity)s, %(target)s, %(evidence)s, %(agent)s,
                           %(created_at)s, %(weight)s)
                   ON CONFLICT (finding_id) DO UPDATE SET
                     weight = EXCLUDED.weight, created_at = EXCLUDED.created_at,
                     title = EXCLUDED.title, detail = EXCLUDED.detail""", d)
        self._conn.commit()
        return finding.finding_id

    def hot(self, threshold: float = 0.2, limit: int = 50) -> list[Finding]:
        if not self._conn:
            raise ConnectionError("PostgresBoard not connected")
        now = time.time()
        with self._conn.cursor() as cur:
            cur.execute(
                f"""SELECT finding_id, ftype, title, detail, severity, target,
                           evidence, agent, created_at, weight
                    FROM swarm_findings
                    WHERE weight * POWER(0.5, (%s - created_at) / ({_half_life_case()}))
                          >= %s
                    ORDER BY weight * POWER(0.5, (%s - created_at) /
                             ({_half_life_case()})) DESC
                    LIMIT %s""", (now, threshold, now, limit))
            rows = cur.fetchall()
        out = []
        for r in rows:
            out.append(Finding(finding_id=r[0], ftype=r[1], title=r[2],
                               detail=r[3], severity=r[4], target=r[5],
                               evidence=r[6], agent=r[7],
                               created_at=r[8], weight=r[9]))
        return out

    def count(self) -> int:
        if not self._conn:
            return 0
        with self._conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM swarm_findings")
            return cur.fetchone()[0]

    # -- vectors --------------------------------------------------------
    def ensure_vector(self) -> bool:
        """Enable pgvector column. False when extension unavailable (fail open)."""
        if not self._conn:
            raise ConnectionError("PostgresBoard not connected")
        try:
            with self._conn.cursor() as cur:
                cur.execute(VECTOR_SQL.format(dim=self.dim))
            self._conn.commit()
            self._vector_ready = True
            return True
        except Exception as e:
            self.error = str(e)[:300]
            try:
                self._conn.rollback()
            except Exception:
                pass
            return False

    def write_with_embedding(self, finding: Finding) -> str:
        """Write + store embedding. Falls back to plain write without vectors."""
        fid = self.write(finding)
        if not self._vector_ready:
            return fid
        try:
            vec = self._embed(f"{finding.ftype} {finding.title} {finding.detail}")
            with self._conn.cursor() as cur:
                cur.execute(
                    "UPDATE swarm_findings SET embedding = %s WHERE finding_id = %s",
                    (vec, fid))
            self._conn.commit()
        except Exception:
            try:
                self._conn.rollback()
            except Exception:
                pass
        return fid

    def similar(self, query: str, top_k: int = 5) -> list[Finding]:
        """Cosine-similar findings (`<=>`). Empty when vectors unavailable."""
        if not self._conn or not self._vector_ready:
            return []
        try:
            vec = self._embed(query)
            with self._conn.cursor() as cur:
                cur.execute(
                    """SELECT finding_id, ftype, title, detail, severity, target,
                              evidence, agent, created_at, weight
                       FROM swarm_findings
                       WHERE embedding IS NOT NULL
                       ORDER BY embedding <=> %s::vector
                       LIMIT %s""", (vec, top_k))
                rows = cur.fetchall()
            return [Finding(finding_id=r[0], ftype=r[1], title=r[2],
                            detail=r[3], severity=r[4], target=r[5],
                            evidence=r[6], agent=r[7],
                            created_at=r[8], weight=r[9]) for r in rows]
        except Exception:
            return []
