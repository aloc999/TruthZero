"""TRUTHZERO Swarm — stigmergic blackboard inspired by Pentest-Swarm-AI.

Three primitives (vs a fixed pipeline):
- Stigmergy: agents coordinate via shared blackboard, not a central planner.
- Emergence: attack chains appear from blackboard state, not prescribed order.
- Decentralization: each agent has its own trigger predicate.
"""
from truthzero.swarm.blackboard import Blackboard, Finding, FINDING_HALF_LIVES
from truthzero.swarm.agents import SWARM_AGENTS, SwarmAgentSpec
from truthzero.swarm.scheduler import SwarmScheduler, SwarmResult
from truthzero.swarm.toolchain import TOOLCHAIN, ToolchainManager
from truthzero.swarm.pgboard import PostgresBoard, SCHEMA_SQL, VECTOR_SQL, dsn_from_env, hashing_embed
from truthzero.swarm.selfheal import plan_heal, should_retry, HealPlan
from truthzero.swarm.miner import mine
from truthzero.swarm.specialists import (
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
    "VECTOR_SQL",
    "dsn_from_env",
    "hashing_embed",
    "plan_heal",
    "should_retry",
    "HealPlan",
    "mine",
    "auth_holder_spec",
    "param_fuzzer_spec",
    "chain_builder_spec",
    "maybe_spawn",
]
