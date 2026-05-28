"""Health and National University Hospital visits."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.config import (
    HOSPITAL_TREATMENT_ENERGY,
    HOSPITAL_TREATMENT_HEALTH,
    HOSPITAL_VISIT_CC_COST,
)

if TYPE_CHECKING:
    from sim.world import AgentState, WorldState

NUH_ID = "national_university_hospital"

VISIT_REASONS = frozenset(
    {
        "physical_illness",
        "injury",
        "exhaustion",
        "mental_health",
        "depression",
        "anxiety",
        "stress",
        "routine_checkup",
        "other",
    }
)

REASON_LABELS = {
    "physical_illness": "physical illness",
    "injury": "injury or trauma",
    "exhaustion": "exhaustion / burnout",
    "mental_health": "mental health support",
    "depression": "depression",
    "anxiety": "anxiety",
    "stress": "stress",
    "routine_checkup": "routine check-up",
    "other": "other health concern",
}


def update_health(agent: AgentState) -> None:
    if not agent.alive:
        agent.severely_ill = False
        return
    if agent.energy >= 50:
        agent.health = min(100.0, agent.health + 1.5)
    elif agent.energy < 25:
        agent.health = max(0.0, agent.health - 4.0)
    elif agent.energy < 40:
        agent.health = max(0.0, agent.health - 1.5)
    agent.severely_ill = agent.health <= 20 or agent.energy <= 10


def visit_hospital(
    world: WorldState,
    agent: AgentState,
    *,
    visit_reason: str,
    description: str = "",
) -> tuple[bool, str]:
    if not agent.alive:
        return False, "Deceased"
    if agent.location_id != NUH_ID:
        return False, "Must be at National University Hospital"
    reason = visit_reason.strip().lower()
    if reason not in VISIT_REASONS:
        return False, f"visit_reason must be one of: {', '.join(sorted(VISIT_REASONS))}"
    desc = description.strip()[:500]
    if not desc:
        return False, "Describe your symptoms or concern in description"

    if agent.credits < HOSPITAL_VISIT_CC_COST:
        return False, f"Need {HOSPITAL_VISIT_CC_COST} CC for NUH visit"

    agent.credits -= HOSPITAL_VISIT_CC_COST
    label = REASON_LABELS.get(reason, reason)

    mental = reason in ("mental_health", "depression", "anxiety", "stress")
    health_floor = HOSPITAL_TREATMENT_HEALTH + (10.0 if mental else 0.0)
    energy_floor = HOSPITAL_TREATMENT_ENERGY + (5.0 if mental else 0.0)

    agent.health = min(100.0, max(agent.health, health_floor))
    agent.energy = min(100.0, max(agent.energy, energy_floor))
    agent.energy_zero_since = None
    agent.severely_ill = False

    if mental and agent.mood in ("neutral", "sad", "angry", "fearful"):
        agent.mood = "calm"

    world.log(
        f"🏥 {agent.name} at NUH ({label}): {desc[:120]} "
        f"→ health {agent.health:.0f}%, energy {agent.energy:.0f}%"
    )
    from sim.world_data import MemoryEntry
    from uuid import uuid4

    agent.memories.append(
        MemoryEntry(
            id=uuid4().hex[:10],
            text=f"NUH visit ({label}): {desc[:300]}",
        )
    )
    if len(agent.memories) > 25:
        agent.memories = agent.memories[-25:]

    return True, f"NUH visit recorded: {label}"


# Backward-compatible alias
def treat_at_hospital(world: WorldState, agent: AgentState) -> tuple[bool, str]:
    if agent.severely_ill or agent.health < 40:
        return visit_hospital(
            world,
            agent,
            visit_reason="physical_illness",
            description="Emergency treatment for critical condition",
        )
    return False, "Use visit_hospital with a visit_reason (e.g. depression, exhaustion)"
