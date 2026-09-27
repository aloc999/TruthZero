"""Swarm specialist agents — trigger predicates + prompts.

Four independent agents (mirrors Pentest-Swarm-AI):
- recon: maps attack surface, always fires first / on new scope.
- classify: triages raw findings into severity + exploitability.
- exploit: proves vulns with safe PoC, captures evidence.
- report: writes evidence-backed findings (SARIF/markdown).

Decentralization: each agent runs its own trigger predicate against the
blackboard. Add a new agent with its own predicate — no orchestrator rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from zer0code.swarm.blackboard import (
    Blackboard, CLASSIFY_THRESHOLD, EXPLOIT_THRESHOLD,
)


@dataclass
class SwarmAgentSpec:
    name: str
    description: str
    threshold: float
    watch_types: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    system_prompt: str = ""

    def should_fire(self, board: Blackboard, round_no: int = 0) -> bool:
        """Trigger predicate — decentralized, per-agent."""
        if self.name == "recon":
            # Fires on round 0 (seed) or when fresh scope/targets appear
            # with no hot findings yet.
            return round_no == 0 or len(board.hot()) == 0
        hot = board.hot(self.threshold, self.watch_types or None)
        return len(hot) > 0


RECON_PROMPT = """You are the RECON specialist in a pentest swarm.
Map attack surface fast and write findings to the blackboard:
- Subdomains (subfinder/crt.sh), alive hosts (httpx/probe), ports (naabu/nmap top-1000),
  tech fingerprint, content discovery (ffuf/dir fuzz), JS endpoints + secrets, crawl.
Rules: scope-only targets. One finding per fact (PORT_OPEN, SUBDOMAIN, ENDPOINT,
TECH, OBJECT_REF for mined ids/UUIDs/emails). No exploitation — just map."""

CLASSIFY_PROMPT = """You are the CLASSIFY specialist in a pentest swarm.
Triage hot blackboard findings (weight >= 0.2):
- Confirm/deny with a single cheap probe (headers, replay, introspection).
- Assign severity (critical/high/medium/low/info) + exploitability (proven/likely/possible/fp).
- Mark false positives so the exploit agent skips them; reinforce real ones.
- Mine every response for object references (ids, UUIDs, emails) → OBJECT_REF findings
  so other agents can turn one leak into cross-user BOLA/IDOR probes."""

EXPLOIT_PROMPT = """You are the EXPLOIT specialist in a pentest swarm.
Only pursue findings with weight >= 0.5:
- Prove with SAFE PoC: BOLA/IDOR (swap IDs across users), JWT forgery/confusion,
  mass assignment, SSRF (OOB/collaborator, never internal destruction), SQLi/NoSQLi,
  XSS (alert-less proof), auth bypass, SSTI, file upload, race (single-packet concept).
- Capture evidence: full request/response, timing, screenshots where useful.
- On success write VULN_CONFIRMED (reinforces pheromone); on clean failure let it decay.
- Chain: a low finding + another low finding = re-test as combined path."""

REPORT_PROMPT = """You are the REPORT specialist in a pentest swarm.
Turn VULN_CONFIRMED findings into evidence-backed reports:
- Title, CVSS 3.1 vector + score, severity, description, steps to reproduce,
  PoC (request/response), impact, remediation. No theoretical bugs — every
  finding must cite captured evidence from the blackboard."""

SWARM_AGENTS: list[SwarmAgentSpec] = [
    SwarmAgentSpec(
        name="recon",
        description="Attack-surface mapping (subdomains, ports, tech, dirs, JS)",
        threshold=0.0,
        watch_types=[],
        tools=["subdomain_enum", "port_scan", "tech_detect", "dir_fuzz",
               "web_crawl", "js_analyze", "dns_lookup", "whois_lookup",
               "http_replay", "nuclei_scan"],
        system_prompt=RECON_PROMPT,
    ),
    SwarmAgentSpec(
        name="classify",
        description="Triage + severity + FP filtering + object-ref mining",
        threshold=CLASSIFY_THRESHOLD,
        watch_types=[],
        tools=["http_replay", "web_fetch", "response_diff", "timing_attack",
               "tech_detect", "js_analyze"],
        system_prompt=CLASSIFY_PROMPT,
    ),
    SwarmAgentSpec(
        name="exploit",
        description="Safe PoC + evidence capture + chaining",
        threshold=EXPLOIT_THRESHOLD,
        watch_types=["VULN", "OBJECT_REF", "ENDPOINT", "TECH", "SECRET",
                     "TAKEOVER_CANDIDATE", "CREDS"],
        tools=["http_replay", "payload_gen", "auth_session", "oob_server",
               "response_diff", "timing_attack", "exploit_chain", "bash",
               "screenshot", "web_fetch"],
        system_prompt=EXPLOIT_PROMPT,
    ),
    SwarmAgentSpec(
        name="report",
        description="Evidence-backed reporting (markdown + SARIF)",
        threshold=0.0,
        watch_types=["VULN_CONFIRMED"],
        tools=["write_file", "read_file"],
        system_prompt=REPORT_PROMPT,
    ),
]


def get_agent(name: str) -> SwarmAgentSpec | None:
    for a in SWARM_AGENTS:
        if a.name == name:
            return a
    return None
