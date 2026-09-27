"""On-demand specialist sub-agents — spawned at runtime, torn down when done.

The scheduler registers these dynamically (no orchestrator rewrite):
- auth-holder: owns a session (login, refresh, attach creds to replays)
- param-fuzzer: takes a discovered endpoint+param, fuzzes merge/pollution/injection
- chain-builder: takes 2+ low findings, re-tests them as one combined path

Each spec carries its own trigger predicate over the blackboard.
"""
from __future__ import annotations

from zer0code.swarm.agents import SwarmAgentSpec
from zer0code.swarm.blackboard import Blackboard


def auth_holder_spec() -> SwarmAgentSpec:
    return SwarmAgentSpec(
        name="auth-holder",
        description="Owns a session: login, refresh, supply creds to replays",
        threshold=0.0,
        watch_types=["ENDPOINT"],
        tools=["auth_session", "http_replay", "response_diff"],
        system_prompt=(
            "You are the AUTH-HOLDER. Get and keep ONE working session: "
            "try login/register flow, store cookies/JWT via auth_session, "
            "refresh on 401 (see self-heal rules), publish SESSION findings "
            "so exploit agents replay with your creds."),
    )


def param_fuzzer_spec(endpoint: str = "", param: str = "") -> SwarmAgentSpec:
    return SwarmAgentSpec(
        name=f"param-fuzzer:{param or 'general'}",
        description=f"Fuzz {param or 'params'} on {endpoint or 'target'} then die",
        threshold=0.0,
        watch_types=["OBJECT_REF", "ENDPOINT"],
        tools=["http_replay", "payload_gen", "response_diff", "timing_attack"],
        system_prompt=(
            f"You are a PARAM-FUZZER for endpoint {endpoint} param {param}. "
            "Test: type juggling, pollution (&a=1&a=2), prototype keys "
            "(__proto__/constructor), injection probes per class, boundary "
            "values. Write VULN or OBJECT_REF findings, then terminate."),
    )


def chain_builder_spec() -> SwarmAgentSpec:
    return SwarmAgentSpec(
        name="chain-builder",
        description="Combine 2+ low findings into one path, re-test jointly",
        threshold=0.0,
        watch_types=["VULN"],
        tools=["http_replay", "exploit_chain", "response_diff"],
        system_prompt=(
            "You are the CHAIN-BUILDER. Pick 2+ low/medium VULN findings on "
            "the same target and re-test them as ONE path (e.g. info-disclose "
            "→ id → BOLA; XSS → session → auth). Write VULN_CONFIRMED with "
            "the full chain as evidence, or let them decay."),
    )


def maybe_spawn(board: Blackboard, scheduler) -> list[str]:
    """Emergence helper: spawn specialists when board state warrants it.

    Returns names of spawned agents. Idempotent per scheduler lifetime.
    """
    spawned: list[str] = []
    existing = {a.name for a in scheduler.agents}
    vulns = [f for f in board.hot() if f.ftype == "VULN"]
    if len(vulns) >= 2 and "chain-builder" not in existing:
        scheduler.register_agent(chain_builder_spec())
        spawned.append("chain-builder")
    sessions = [f for f in board.hot() if f.ftype == "SESSION"]
    endpoints = [f for f in board.hot() if f.ftype == "ENDPOINT"]
    if endpoints and not sessions and "auth-holder" not in existing:
        scheduler.register_agent(auth_holder_spec())
        spawned.append("auth-holder")
    return spawned
