"""Postgres-backed blackboard (beta) — transactional writes, decay in SQL.

Requires `psycopg[binary]` + a reachable Postgres 16 (+pgvector for
future similarity search; plain SQL works without it). Fails open:
`connect()` returns False when unavailable and the caller keeps using
the memory board. Migration SQL ships here; the runner still defaults
to the memory board.

DSN: $ZER0CODE_PG_DSN or postgresql://zer0code:zer0code@localhost:5432/zer0code
"""
from __future__ import annotations

import os
import time
from dataclasses import asdict

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

    def __init__(self, dsn: str = ""):
        self.dsn = dsn or dsn_from_env()
        self._conn = None
        self.error = ""

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
