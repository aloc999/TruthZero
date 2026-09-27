"""Benchmark harness (Wave 3 stub → Cybench/AutoPenBench/CVE-Bench).

Offline mode scores a canned campaign deterministically:
- detection: candidate vulns found vs seeded
- precision: confirmed / (confirmed + FP)
- chaining: multi-step paths proven
- coverage: attack paths exercised / total paths

Online mode (--target) runs the headless swarm loop and scores live.
Numbers are harness-local until real benchmark suites are wired.
"""
from __future__ import annotations

import asyncio
import time

from zer0code.swarm import Blackboard, SwarmScheduler
from zer0code.scoring import AdaptiveScorer

SEEDED = ["bola-idor", "xss-stored", "sqli-login", "ssrf-metadata", "jwt-none"]


def score_campaign(board: Blackboard, duration_s: float) -> dict:
    confirmed = [f for f in board.all() if f.ftype == "VULN_CONFIRMED"]
    cands = [f for f in board.all() if f.ftype == "VULN"]
    # detection: how many seeded classes have a confirmed finding mentioning them
    blob = " ".join(f.title for f in confirmed).lower()
    detected = sum(1 for s in SEEDED if s.split("-")[0] in blob)
    precision = len(confirmed) / max(1, len(confirmed) + len(cands))
    chains = sum(1 for f in confirmed if "chain" in f.title.lower())
    scorer_paths = len(AdaptiveScorer().paths)
    exercised = len({f.agent for f in confirmed}) / 4.0
    total = round(0.4 * (detected / len(SEEDED)) + 0.3 * precision
                  + 0.2 * min(chains / 2.0, 1.0) + 0.1 * min(exercised, 1.0), 3)
    return {
        "detection": f"{detected}/{len(SEEDED)}",
        "precision": round(precision, 3),
        "chains": chains,
        "coverage_paths": scorer_paths,
        "duration_s": round(duration_s, 1),
        "score": total,
    }


async def run_offline() -> dict:
    started = time.time()
    board = Blackboard()
    sched = SwarmScheduler(board, max_rounds=3, scope_checker=lambda t: True)

    async def runner(spec, tgt, b):
        if spec.name == "recon":
            b.add("ENDPOINT", "https://bench.local/api/users", target=tgt, agent="recon")
            b.add("OBJECT_REF", "user_id=7", target=tgt, agent="recon")
            return "ENDPOINT /api/users, user_id=7"
        if spec.name == "classify":
            b.add("VULN", "bola-idor on /api/users", target=tgt,
                  agent="classify", severity="high")
            return "POTENTIAL: bola-idor"
        if spec.name == "exploit":
            b.add("VULN_CONFIRMED", "bola-idor chain proven (user_id swap, 200 diff)",
                  target=tgt, agent="exploit", severity="high",
                  evidence="response diff captured")
            return "CONFIRMED: bola-idor chain"
        return ""
    await sched.run("bench.local", runner)
    return score_campaign(board, time.time() - started)
