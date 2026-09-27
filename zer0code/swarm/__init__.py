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
]
