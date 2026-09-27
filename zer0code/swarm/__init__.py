"""ZER0CODE Swarm — stigmergic blackboard inspired by Pentest-Swarm-AI.

Three primitives (vs a fixed pipeline):
- Stigmergy: agents coordinate via shared blackboard, not a central planner.
- Emergence: attack chains appear from blackboard state, not prescribed order.
- Decentralization: each agent has its own trigger predicate.
"""
from zer0code.swarm.blackboard import Blackboard, Finding, FINDING_HALF_LIVES
from zer0code.swarm.agents import SWARM_AGENTS, SwarmAgentSpec
from zer0code.swarm.scheduler import SwarmScheduler, SwarmResult
from zer0code.swarm.toolchain import TOOLCHAIN, ToolchainManager
from zer0code.swarm.pgboard import PostgresBoard, SCHEMA_SQL, dsn_from_env
from zer0code.swarm.selfheal import plan_heal, should_retry, HealPlan
from zer0code.swarm.miner import mine
from zer0code.swarm.specialists import (
    auth_holder_spec, param_fuzzer_spec, chain_builder_spec, maybe_spawn,
)

__all__ = [
    "Blackboard",
    "Finding",
    "FINDING_HALF_LIVES",
    "SWARM_AGENTS",
    "SwarmAgentSpec",
    "SwarmScheduler",
    "SwarmResult",
    "TOOLCHAIN",
    "ToolchainManager",
    "PostgresBoard",
    "SCHEMA_SQL",
    "dsn_from_env",
    "plan_heal",
    "should_retry",
    "HealPlan",
    "mine",
    "auth_holder_spec",
    "param_fuzzer_spec",
    "chain_builder_spec",
    "maybe_spawn",
]
