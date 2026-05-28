"""Energy, knowledge, and influence needs (docs/ORCHESTRATION.md)."""

from __future__ import annotations

import time

from sim.config import (
    INFLUENCE_DECAY_HOURS,
    KNOWLEDGE_DECAY_HOURS,
    SIM_TIME_SCALE,
)
from sim.vitality import apply_energy_decay_for_agent
from sim.world import AgentState, WorldState


def _scaled_seconds(hours: float) -> float:
    return hours * 3600.0 / max(SIM_TIME_SCALE, 0.001)


def apply_agent_needs_decay(
    world: WorldState,
    agent: AgentState,
    *,
    dt: float,
    now: float | None = None,
) -> bool:
    """Decay needs for one agent over ``dt`` seconds (length of their turn only).

    Call at end of turn with ``dt = time.time() - turn_started_at`` so agents
    do not pay for wall-clock while other agents are thinking.
    Returns True if the agent died from energy depletion.
    """
    if not agent.alive:
        return False
    now = now or time.time()
    dt = max(0.0, dt)

    died = apply_energy_decay_for_agent(world, agent, now, dt=dt)

    k_rate = 100.0 / _scaled_seconds(KNOWLEDGE_DECAY_HOURS)
    i_rate = 100.0 / _scaled_seconds(INFLUENCE_DECAY_HOURS)
    agent.knowledge = max(0.0, agent.knowledge - k_rate * dt)
    agent.influence = max(0.0, agent.influence - i_rate * dt)

    return died


def bump_knowledge(agent: AgentState, amount: float = 25.0) -> None:
    agent.knowledge = min(100.0, agent.knowledge + amount)


def bump_influence(agent: AgentState, amount: float = 15.0) -> None:
    agent.influence = min(100.0, agent.influence + amount)


def needs_summary(agent: AgentState) -> str:
    parts = [f"energy {agent.energy:.0f}%"]
    if agent.knowledge < 30:
        parts.append(f"knowledge {agent.knowledge:.0f}% (low — visit National Library)")
    else:
        parts.append(f"knowledge {agent.knowledge:.0f}%")
    if agent.influence < 30:
        parts.append(f"influence {agent.influence:.0f}% (low — socialize)")
    else:
        parts.append(f"influence {agent.influence:.0f}%")
    return ", ".join(parts)
