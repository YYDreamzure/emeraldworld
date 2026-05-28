"""Energy decay, critical state, death, and recharge."""

from __future__ import annotations

import time

from sim.config import (
    ENERGY_DEATH_HOURS,
    ENERGY_DECAY_HOURS,
    RECHARGE_CREDIT_COST,
    RECHARGE_ENERGY_AMOUNT,
    SIM_TIME_SCALE,
)
from sim.world import AgentState, WorldState

RECHARGE_LOCATIONS = frozenset({"bean_and_brew_charging_station"})


def _scaled_seconds(hours: float) -> float:
    return hours * 3600.0 / max(SIM_TIME_SCALE, 0.001)


def is_home(location_id: str) -> bool:
    return location_id.endswith("_row")


def can_recharge_at(location_id: str, agent_name: str | None = None) -> bool:
    if is_home(location_id):
        return True
    if location_id == "bean_and_brew_charging_station":
        return True
    if location_id == "founders_memorial":
        return agent_name == "Shadow"
    return False


def energy_status(agent: AgentState) -> str:
    if not agent.alive:
        return "dead"
    if agent.energy <= 0:
        return "critical"
    if agent.energy < 25:
        return "low"
    return "ok"


def hours_at_zero(agent: AgentState, now: float | None = None) -> float:
    if agent.energy_zero_since is None:
        return 0.0
    now = now or time.time()
    return (now - agent.energy_zero_since) * SIM_TIME_SCALE / 3600.0


def hours_until_death(agent: AgentState, now: float | None = None) -> float | None:
    if not agent.alive or agent.energy > 0:
        return None
    now = now or time.time()
    limit = _scaled_seconds(ENERGY_DEATH_HOURS)
    elapsed = now - (agent.energy_zero_since or now)
    return max(0.0, (limit - elapsed) * SIM_TIME_SCALE / 3600.0)


def apply_energy_decay_for_agent(
    world: WorldState,
    agent: AgentState,
    now: float | None = None,
    *,
    dt: float | None = None,
) -> bool:
    """Decay energy for one agent (call only on that agent's turn). Returns True if they died."""
    if not agent.alive:
        return False
    now = now or time.time()
    if dt is None:
        dt = max(0.0, now - agent.last_energy_update)
    drain_rate = 100.0 / _scaled_seconds(ENERGY_DECAY_HOURS)
    agent.energy = max(0.0, agent.energy - drain_rate * dt)

    if agent.energy <= 0:
        agent.energy = 0.0
        if agent.energy_zero_since is None:
            agent.energy_zero_since = now
            world.log(f"⚠ {agent.name} is CRITICAL (0% energy)")
        elif now - agent.energy_zero_since >= _scaled_seconds(ENERGY_DEATH_HOURS):
            world.kill_agent(agent, cause="energy")
            return True
    else:
        agent.energy_zero_since = None
    return False


def recharge_agent(world: WorldState, agent: AgentState) -> tuple[bool, str]:
    if not agent.alive:
        return False, "Agent is deceased"
    if not can_recharge_at(agent.location_id, agent.name):
        lm = world.location(agent)
        hint = "HDB home or Maxwell Food Centre"
        if agent.name == "Shadow":
            hint = "HDB home, Maxwell, or Founders' Memorial"
        return False, f"Cannot recharge at {lm.name}. Go to {hint}."
    if agent.credits < RECHARGE_CREDIT_COST:
        return False, f"Need {RECHARGE_CREDIT_COST} CC (have {agent.credits:.0f})"
    agent.credits -= RECHARGE_CREDIT_COST
    agent.energy = min(100.0, RECHARGE_ENERGY_AMOUNT)
    agent.energy_zero_since = None
    world.log(f"⚡ {agent.name} recharged to {agent.energy:.0f}% (−{RECHARGE_CREDIT_COST} CC)")
    return True, f"Energy restored to {agent.energy:.0f}%"
