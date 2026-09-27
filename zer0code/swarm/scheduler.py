"""Swarm scheduler — concurrent specialists reacting to the blackboard.

Emergent loop (no fixed order):
  round 0: recon fires (seed).
  each round: every agent evaluates its own trigger predicate;
  fired agents run CONCURRENTLY (asyncio); their tool outputs are
  parsed into new findings; exploit results feed back and wake others;
  stale paths decay and die (prune).

Scope is enforced at the tool layer AND again here (defence in depth).
Cleanup hooks are registered BEFORE execution (reverse-order on exit).
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from zer0code.swarm.agents import SWARM_AGENTS, SwarmAgentSpec
from zer0code.swarm.blackboard import Blackboard


@dataclass
class SwarmResult:
    target: str
    rounds: int
    agents_fired: dict[str, int] = field(default_factory=dict)
    findings_total: int = 0
    confirmed: int = 0
    duration_s: float = 0.0
    stopped_reason: str = ""


class SwarmScheduler:
    def __init__(
        self,
        board: Blackboard | None = None,
        max_rounds: int = 6,
        max_concurrent: int = 4,
        scope_checker: Callable[[str], bool] | None = None,
    ):
        self.board = board or Blackboard()
        self.max_rounds = max_rounds
        self.max_concurrent = max_concurrent
        self.scope_checker = scope_checker
        self.agents: list[SwarmAgentSpec] = list(SWARM_AGENTS)

    def register_agent(self, spec: SwarmAgentSpec) -> None:
        """Decentralization: new agent joins without orchestrator rewrite."""
        self.agents.append(spec)

    # -- scope (second enforcement layer; tool layer is the first) -------
    def _in_scope(self, target: str) -> bool:
        if not self.scope_checker:
            return True
        try:
            return bool(self.scope_checker(target))
        except Exception:
            return False

    # -- finding extraction from raw agent output --------------------------
    def ingest_text(self, agent_name: str, target: str, text: str) -> int:
        """Parse free-text agent output into structured findings. Returns count."""
        if not text:
            return 0
        count = 0
        existing = {(f.ftype, f.title) for f in self.board.all()}
        # confirmed vuln markers
        for m in re.finditer(
            r"(CONFIRMED|VULN_CONFIRMED|P1|CRITICAL\s+VULN)\s*[:\-]\s*(.+)",
            text, re.IGNORECASE,
        ):
            self.board.add("VULN_CONFIRMED", m.group(2).strip()[:200],
                           detail=text[:2000], agent=agent_name,
                           target=target, severity="high",
                           evidence=text[:4000])
            count += 1
        # candidate vuln markers
        for m in re.finditer(
            r"(POTENTIAL|CANDIDATE|SUSPECTED)\s*[:\-]\s*(.+)",
            text, re.IGNORECASE,
        ):
            self.board.add("VULN", m.group(2).strip()[:200],
                           detail=text[:2000], agent=agent_name,
                           target=target, severity="medium")
            count += 1
        # response mining: every output becomes leads (Wave 3 runtime reaction)
        try:
            from zer0code.swarm.miner import mine as _mine
            endpoints_kept = 0
            for lead in _mine(text, source=agent_name, target=target):
                if (lead["ftype"], lead["title"]) in existing:
                    continue
                # ENDPOINT leads are noisy — keep max 5 per ingest;
                # endpoints otherwise come from recon proper.
                if lead["ftype"] == "ENDPOINT" and lead["severity"] != "high":
                    if endpoints_kept >= 5:
                        continue
                    endpoints_kept += 1
                self.board.add(lead["ftype"], lead["title"],
                               detail=lead.get("detail", ""), agent=agent_name,
                               target=target, severity=lead.get("severity", "info"))
                existing.add((lead["ftype"], lead["title"]))
                count += 1
                if count >= 25:
                    break
        except Exception:
            pass
        return count

    # -- main loop ----------------------------------------------------------
    async def run(
        self,
        target: str,
        agent_runner: Callable[[SwarmAgentSpec, str, Blackboard], Any],
        budget_s: float = 0,
    ) -> SwarmResult:
        started = time.time()
        if not self._in_scope(target):
            return SwarmResult(target=target, rounds=0,
                               stopped_reason=f"target out of scope: {target}")
        fired: dict[str, int] = {a.name: 0 for a in self.agents}
        rounds = 0
        sem = asyncio.Semaphore(self.max_concurrent)

        async def _fire(spec: SwarmAgentSpec) -> int:
            async with sem:
                try:
                    out = await agent_runner(spec, target, self.board)
                    if isinstance(out, str):
                        return self.ingest_text(spec.name, target, out)
                    return 0
                except Exception:
                    return 0

        for round_no in range(self.max_rounds):
            if budget_s and (time.time() - started) > budget_s:
                return SwarmResult(target, rounds, fired,
                                   len(self.board.all()),
                                   self._confirmed(), time.time() - started,
                                   "budget exhausted")
            # Wave 3 emergence: spawn on-demand specialists when warranted.
            try:
                from zer0code.swarm.specialists import maybe_spawn as _spawn
                for name in _spawn(self.board, self):
                    fired[name] = fired.get(name, 0)
            except Exception:
                pass
            to_fire = [a for a in self.agents if a.should_fire(self.board, round_no)]
            if not to_fire:
                self.board.prune_stale()
                rounds = round_no + 1
                break
            # report agent only fires when there is something to report
            results = await asyncio.gather(*[_fire(a) for a in to_fire])
            for spec, _ in zip(to_fire, results):
                fired[spec.name] = fired.get(spec.name, 0) + 1
            self.board.prune_stale()
            rounds = round_no + 1
            # emergence stop: nothing hot and no new findings this round
            if sum(results) == 0 and not self.board.hot():
                break

        return SwarmResult(
            target=target, rounds=rounds, agents_fired=fired,
            findings_total=len(self.board.all()),
            confirmed=self._confirmed(),
            duration_s=time.time() - started,
            stopped_reason="completed",
        )

    def _confirmed(self) -> int:
        return sum(1 for f in self.board.all() if f.ftype == "VULN_CONFIRMED")

    def status_line(self) -> str:
        s = self.board.summary()
        return (f"Swarm board: {s['total']} findings ({s['hot']} hot) "
                f"by_type={s['by_type']} by_sev={s['by_severity']}")
