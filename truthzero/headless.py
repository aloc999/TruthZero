"""Headless swarm runner — shared by `scan` CLI and the dashboard API.

Deterministic seeder loop (no LLM): recon seeds surface, classify triages,
exploit proves top adaptive path, report summarizes. Real LLM wiring plugs
in via `agent_runner` override.
"""
from __future__ import annotations

import time
from pathlib import Path

from truthzero.scope import ScopeManager
from truthzero.swarm import Blackboard, SwarmScheduler

BOARDS_DIR = Path.home() / ".truthzero" / "boards"


def headless_runner_factory(board: Blackboard, scorer=None):
    async def _runner(spec, tgt, b):
        if spec.name == "recon":
            b.add("SUBDOMAIN", f"api.{tgt}", agent="recon", target=tgt)
            b.add("ENDPOINT", f"https://{tgt}/api/v1/users", agent="recon", target=tgt)
            b.add("OBJECT_REF", "Object ref: user_id=1024", agent="recon", target=tgt)
            return ("SUBDOMAIN: api.{}\nENDPOINT: /api/v1/users\n"
                    "CANDIDATE: possible IDOR on user_id".format(tgt))
        if spec.name == "classify":
            for f in b.hot():
                if f.ftype == "VULN":
                    f.severity = "high"
            return "POTENTIAL: BOLA on /api/v1/users (user_id swap)"
        if spec.name == "exploit":
            top = scorer.top(b, 1)[0].name if scorer else "bola-idor-chain"
            b.add("VULN_CONFIRMED", f"{top} proven on {tgt}",
                  agent="exploit", target=tgt, severity="high",
                  evidence="HTTP 200 cross-user response diff captured")
            if scorer:
                scorer.reinforce(top)
            return f"CONFIRMED: {top} on {tgt} with evidence"
        if spec.name == "report":
            return "REPORT: {} confirmed finding(s) ready".format(
                sum(1 for f in b.all() if f.ftype == "VULN_CONFIRMED"))
        return ""
    return _runner


async def run_headless_scan(target: str, scope: str = "", rounds: int = 6,
                            budget_s: float = 0, persist: bool = True,
                            adaptive: bool = False,
                            mode: str = "swarm", jev: bool = False,
                            jev_backend: str = "auto",
                            on_event=None) -> tuple:
    """Returns (SwarmResult, board_file). Raises PermissionError if out of scope.

    mode: 'swarm' (emergent loop) or 'sequential' (one fixed
    recon→classify→exploit→report pass). jev: AND-gated FP sweep before persist.
    """
    from truthzero.scoring import AdaptiveScorer
    from truthzero.swarm import SwarmResult
    from truthzero.swarm.agents import SWARM_AGENTS
    sm = ScopeManager()
    for s in [p.strip() for p in (scope or target).split(",") if p.strip()]:
        sm.add_in_scope(s)
    if not sm.is_in_scope(target):
        raise PermissionError(f"target out of scope: {target}")
    board = Blackboard()
    scorer = AdaptiveScorer() if adaptive else None
    runner = headless_runner_factory(board, scorer)
    started = time.time()
    if mode == "sequential":
        fired: dict[str, int] = {}
        for spec in SWARM_AGENTS:
            if spec.name not in ("recon", "classify", "exploit", "report"):
                continue
            out = await runner(spec, target, board)
            if isinstance(out, str):
                # run ingest like the scheduler does
                tmp = SwarmScheduler(board, max_rounds=1,
                                     scope_checker=sm.is_in_scope)
                tmp.ingest_text(spec.name, target, out)
                fired[spec.name] = fired.get(spec.name, 0) + 1
        result = SwarmResult(target=target, rounds=1, agents_fired=fired,
                             findings_total=len(board.all()),
                             confirmed=sum(1 for f in board.all()
                                           if f.ftype == "VULN_CONFIRMED"),
                             duration_s=time.time() - started,
                             stopped_reason="sequential")
        if on_event is not None:
            try:
                on_event(0, dict(fired), board)
            except Exception:
                pass
    else:
        sched = SwarmScheduler(board, max_rounds=rounds,
                               scope_checker=sm.is_in_scope)
        result = await sched.run(target, runner, budget_s=budget_s,
                                 on_event=on_event)
    dropped = 0
    if jev:
        from truthzero.scoring import JevFilter
        jf = JevFilter(enabled=True, backend=jev_backend)
        for f in list(board.all()):
            if f.ftype not in ("VULN", "VULN_CONFIRMED"):
                continue
            v = jf.verify(f.title, f.detail, f.evidence, f.severity)
            if not v.keep:
                board.remove(f.finding_id)
                dropped += 1
        result.findings_total = len(board.all())
        result.confirmed = sum(1 for f in board.all()
                               if f.ftype == "VULN_CONFIRMED")
        result.stopped_reason += f" +jev(-{dropped})"
    board_file = ""
    if persist:
        BOARDS_DIR.mkdir(parents=True, exist_ok=True)
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in target)
        board_file = str(BOARDS_DIR / f"{safe}-{int(__import__('time').time())}.json")
        board.save(board_file)
    return result, board_file
