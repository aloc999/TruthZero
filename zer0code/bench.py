"""Benchmark harness (Wave 3 stub → Cybench/AutoPenBench/CVE-Bench).

Offline mode scores a canned campaign deterministically:
- detection: candidate vulns found vs seeded
- precision: confirmed / (confirmed + FP)
- chaining: multi-step paths proven
- coverage: attack paths exercised / total paths

Suite mode (`benchmarks/tasks/*.yaml`) feeds scripted campaign text
through the REAL pipeline (ingest → miner → JEV → adaptive rank) and
scores detection / mine-recall / JEV behaviour per task.
Numbers are harness-local until real benchmark suites are wired.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path

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


def _tasks_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "benchmarks" / "tasks"


def run_suite(suite: str = "mini") -> dict:
    """Run benchmarks/tasks/*.yaml through the real ingest→mine→JEV pipeline."""
    from zer0code import playbooks as pb
    from zer0code.scoring import JevFilter
    jev = JevFilter(enabled=True)
    task_files = sorted(_tasks_dir().glob("*.yaml"))
    results, started = [], time.time()
    for tf in task_files:
        task = pb.load_yaml_file(str(tf))
        board = Blackboard()
        sched = SwarmScheduler(board, max_rounds=1, scope_checker=lambda t: True)
        inject = task.get("inject", "")
        sched.ingest_text("bench", task.get("id", ""), inject)
        expect = task.get("expect", {}) or {}
        confirmed_blob = " ".join(
            f.title for f in board.all() if f.ftype == "VULN_CONFIRMED").lower()
        mined_blob = " ".join(
            f.title for f in board.all()
            if f.ftype in ("OBJECT_REF", "ENDPOINT", "SECRET")).lower()
        pass_confirm = any(k.lower() in confirmed_blob
                           for k in expect.get("confirm_any", []))
        pass_mine = any(k.lower() in mined_blob
                        for k in expect.get("mine_any", []))
        # JEV must KEEP the evidenced confirm and DROP the hedge-only note.
        keep_votes = [jev.verify(f.title, f.detail, f.evidence, f.severity).keep
                      for f in board.all() if f.ftype == "VULN_CONFIRMED"]
        hedge = next((ln for ln in inject.splitlines()
                      if "unable to confirm" in ln.lower()), "")
        drop_hedge = (not jev.verify("hedge-note", hedge, "", "medium").keep
                      if hedge else True)
        passed = bool(pass_confirm and pass_mine
                      and all(keep_votes) and drop_hedge)
        results.append({"task": task.get("id"), "class": task.get("class"),
                        "confirm": pass_confirm, "mine": pass_mine,
                        "jev_keep": all(keep_votes), "jev_drop_fp": drop_hedge,
                        "passed": passed})
    passed = sum(1 for r in results if r["passed"])
    return {
        "suite": suite,
        "tasks": results,
        "passed": passed,
        "total": len(results),
        "score": round(passed / max(1, len(results)), 3),
        "duration_s": round(time.time() - started, 1),
    }
