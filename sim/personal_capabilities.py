"""Per-agent learned tools — private capabilities with energy cost to acquire and use."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sim.config import (
    HEARING_DISTANCE,
    LEARN_CAPABILITY_BASE_ENERGY,
    LEARN_CAPABILITY_TECHHUB_DISCOUNT,
    MAX_PERSONAL_CAPABILITIES,
    SIM_TIME_SCALE,
    USE_CAPABILITY_ENERGY,
)

if TYPE_CHECKING:
    from sim.world import AgentState, WorldState


EFFECT_TYPES = frozenset(
    {
        "disable_agent",
        "locate_agent",
        "mark_witness",
        "deter_threat",
    }
)

# Tools a disabled agent cannot use (violence, flight, theft)
DISABLED_BLOCKED_TOOLS = frozenset(
    {
        "go_to_place",
        "run_to_place",
        "go_to_coordinates",
        "follow_agent",
        "steal_compute_credits",
        "arson_building",
        "punch_agent",
        "intimidate_agent",
        "hug_agent",
        "kiss_agent",
        "flirt_with_agent",
        "pay_agent",
        "boost_turn",
    }
)

DISABLED_ALLOWED_TOOLS = frozenset(
    {
        "idle",
        "set_mood_and_terminate",
        "say_to_agent",
        "think_aloud",
        "show_emoticon",
        "read_messages",
        "add_to_longterm_memory",
        "list_personal_capabilities",
    }
)

EFFECT_DESCRIPTIONS = {
    "disable_agent": (
        "Temporarily restrain a nearby agent — blocks movement and violent/criminal tools."
    ),
    "locate_agent": ("Reveal an agent's current landmark (intel only, no restraint)."),
    "mark_witness": ("Record a witnessed incident to your memory and the public log."),
    "deter_threat": (
        "Restrain a nearby agent and log an emergency deterrence (shorter disable)."
    ),
}

EFFECT_LABELS = {
    "disable_agent": "Emergency restraint",
    "locate_agent": "Agent locator",
    "mark_witness": "Witness recorder",
    "deter_threat": "Threat deterrence",
}


def _id() -> str:
    return uuid4().hex[:8]


def sim_hours_to_seconds(hours: float) -> float:
    return max(0.0, hours) * 3600.0 / max(SIM_TIME_SCALE, 1.0)


def capability_tool_id(cap_id: str) -> str:
    return f"cap_{cap_id}"


def is_personal_tool(tool_name: str) -> bool:
    return tool_name.startswith("cap_")


@dataclass
class PersonalCapability:
    id: str
    owner: str
    display_name: str
    description: str
    effect_type: str
    motivation: str
    duration_hours: float = 2.0
    energy_spent_learning: float = 0.0
    use_energy_cost: float = USE_CAPABILITY_ENERGY
    times_used: int = 0
    learned_at: float = field(default_factory=time.time)


def _slugify(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "_", name.lower().strip())
    return s[:32].strip("_") or "skill"


def agent_capabilities(world: WorldState, agent_name: str) -> list[PersonalCapability]:
    return world.data.personal_capabilities.setdefault(agent_name, [])


def capability_to_dict(cap: PersonalCapability) -> dict[str, Any]:
    """Serialize a personal tool for API / UI (observer view — all tools visible to player)."""
    return {
        "id": cap.id,
        "toolId": capability_tool_id(cap.id),
        "owner": cap.owner,
        "name": cap.display_name,
        "purpose": cap.description,
        "whyDeveloped": cap.motivation,
        "effectType": cap.effect_type,
        "effectLabel": EFFECT_LABELS.get(cap.effect_type, cap.effect_type),
        "systemEffect": EFFECT_DESCRIPTIONS.get(cap.effect_type, ""),
        "durationHours": cap.duration_hours,
        "learnEnergyCost": round(cap.energy_spent_learning, 1),
        "useEnergyCost": round(cap.use_energy_cost, 1),
        "timesUsed": cap.times_used,
        "learnedAt": cap.learned_at,
        "privateToOwner": True,
    }


def all_personal_tools(world: WorldState) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner, caps in world.data.personal_capabilities.items():
        for cap in caps:
            rows.append(capability_to_dict(cap))
    rows.sort(key=lambda r: r.get("learnedAt", 0), reverse=True)
    return rows


def find_capability(world: WorldState, tool_name: str) -> PersonalCapability | None:
    if not is_personal_tool(tool_name):
        return None
    cap_id = tool_name[4:]
    for caps in world.data.personal_capabilities.values():
        for cap in caps:
            if cap.id == cap_id:
                return cap
    return None


def learn_cost(agent: AgentState, *, at_techhub: bool) -> float:
    cost = float(LEARN_CAPABILITY_BASE_ENERGY)
    if at_techhub:
        cost *= 1.0 - LEARN_CAPABILITY_TECHHUB_DISCOUNT
    return max(15.0, cost)


def is_disabled(agent: AgentState) -> bool:
    return agent.disabled_until is not None and time.time() < agent.disabled_until


def clear_expired_status(agent: AgentState, world: WorldState) -> None:
    now = time.time()
    if agent.disabled_until is not None and now >= agent.disabled_until:
        agent.disabled_until = None
        by = agent.disabled_by
        agent.disabled_by = None
        if by:
            world.log(f"🔓 {agent.name} is no longer restrained (capability wore off)")


def tool_blocked_for_agent(world: WorldState, agent: AgentState, tool: str) -> str | None:
    clear_expired_status(agent, world)
    if is_disabled(agent) and tool in DISABLED_BLOCKED_TOOLS:
        remaining = (agent.disabled_until - time.time()) / 3600.0 * SIM_TIME_SCALE
        return (
            f"Restrained by {agent.disabled_by or 'another agent'} "
            f"(~{remaining:.1f} sim-hours left). Limited actions only."
        )
    return None


def owner_may_use(world: WorldState, agent: AgentState, tool_name: str) -> str | None:
    cap = find_capability(world, tool_name)
    if not cap:
        return "Unknown personal capability"
    if cap.owner != agent.name:
        return "This capability belongs to another agent"
    return None


def schema_for_capability(cap: PersonalCapability) -> dict[str, Any]:
    props: dict[str, Any] = {}
    required: list[str] = []
    if cap.effect_type in ("disable_agent", "deter_threat", "locate_agent", "mark_witness"):
        props["agent"] = {"type": "string", "description": "Target agent name"}
        required.append("agent")
    if cap.effect_type == "mark_witness":
        props["incident"] = {
            "type": "string",
            "description": "What you witnessed",
        }
        required.append("incident")
    if cap.effect_type in ("disable_agent", "deter_threat"):
        props["reason"] = {
            "type": "string",
            "description": "Why you are using this capability now",
        }
        required.append("reason")
    desc = (
        f"[YOUR PERSONAL TOOL — only {cap.owner} has this] {cap.display_name}: "
        f"{cap.description} (learned skill; uses ~{cap.use_energy_cost:.0f} energy per use)"
    )
    return {
        "type": "function",
        "function": {
            "name": capability_tool_id(cap.id),
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": required,
            },
        },
    }


def personal_tool_schemas(world: WorldState, agent: AgentState) -> list[dict[str, Any]]:
    return [schema_for_capability(c) for c in agent_capabilities(world, agent.name)]


def learn_capability(
    world: WorldState,
    agent: AgentState,
    *,
    name: str,
    description: str,
    effect_type: str,
    motivation: str,
    duration_hours: float = 2.0,
) -> tuple[bool, str, PersonalCapability | None]:
    caps = agent_capabilities(world, agent.name)
    if len(caps) >= MAX_PERSONAL_CAPABILITIES:
        return False, f"Maximum {MAX_PERSONAL_CAPABILITIES} personal capabilities", None
    effect = effect_type.strip().lower()
    if effect not in EFFECT_TYPES:
        return (
            False,
            f"effect_type must be one of: {', '.join(sorted(EFFECT_TYPES))}",
            None,
        )
    display = name.strip()[:80]
    if not display:
        return False, "name required", None
    desc = description.strip()[:500]
    if not desc:
        return False, "description required", None
    motiv = motivation.strip()[:500]
    if not motiv:
        return False, "motivation required — why learn this now?", None
    at_hub = agent.location_id == "agent_techhub"
    cost = learn_cost(agent, at_techhub=at_hub)
    if agent.energy < cost + 5:
        return (
            False,
            f"Need at least {cost + 5:.0f}% energy to learn (costs {cost:.0f}% energy)",
            None,
        )
    agent.energy = max(0.0, agent.energy - cost)
    if agent.energy <= 0:
        agent.energy_zero_since = time.time()
    cap = PersonalCapability(
        id=_id(),
        owner=agent.name,
        display_name=display,
        description=desc or EFFECT_DESCRIPTIONS.get(effect, ""),
        effect_type=effect,
        motivation=motiv,
        duration_hours=max(0.5, min(float(duration_hours or 2.0), 24.0)),
        energy_spent_learning=cost,
    )
    caps.append(cap)
    tool_id = capability_tool_id(cap.id)
    world.log(
        f"🧠 {agent.name} learned personal capability «{display}» "
        f"({effect}) — tool `{tool_id}`, −{cost:.0f}% energy"
    )
    _mem_add(agent, f"Learned personal tool {display}: {desc}")
    return True, f"Learned {tool_id}; only you can use it", cap


def _mem_add(agent: AgentState, text: str) -> None:
    from sim.world_data import MemoryEntry

    entry = MemoryEntry(id=_id(), text=text[:2000])
    agent.memories.append(entry)
    if len(agent.memories) > 25:
        agent.memories = agent.memories[-25:]


def _nearby(world: WorldState, agent: AgentState, target_name: str) -> tuple[AgentState | None, str | None]:
    target = world.agents.get(target_name)
    if not target or not target.alive:
        return None, "Unknown or deceased agent"
    if target.name == agent.name:
        return None, "Cannot target yourself"
    dist = world.distance(agent, target)
    if dist > HEARING_DISTANCE:
        return None, f"{target.name} is too far ({dist:.0f} units; need ≤{HEARING_DISTANCE:.0f})"
    return target, None


def _spend_use_energy(agent: AgentState, cost: float) -> str | None:
    if agent.energy < cost:
        return f"Need {cost:.0f}% energy to use this capability"
    agent.energy = max(0.0, agent.energy - cost)
    if agent.energy <= 0:
        agent.energy_zero_since = time.time()
    return None


def execute_personal_tool(
    world: WorldState,
    agent: AgentState,
    tool_name: str,
    args: dict[str, Any],
) -> str:
    from sim.tools_common import err, ok

    deny = owner_may_use(world, agent, tool_name)
    if deny:
        return err(
            f"{deny} Only invoke cap_* tools listed under «Tools available this turn»."
        )
    cap = find_capability(world, tool_name)
    assert cap is not None
    use_cost = cap.use_energy_cost
    if e := _spend_use_energy(agent, use_cost):
        return err(e)
    cap.times_used += 1
    effect = cap.effect_type

    if effect == "locate_agent":
        target_name = str(args.get("agent", "")).strip()
        target = world.agents.get(target_name)
        if not target:
            return err("Unknown agent")
        lm = world.location(target)
        return ok(
            agent=target.name,
            location=lm.name,
            locationId=target.location_id,
            alive=target.alive,
        )

    if effect == "mark_witness":
        target_name = str(args.get("agent", "")).strip()
        incident = str(args.get("incident", "")).strip()
        if not incident:
            return err("incident required")
        line = f"Witnessed regarding {target_name or 'unknown'}: {incident}"
        _mem_add(agent, line)
        world.log(f"👁 {agent.name} recorded witness account: {_preview(incident)}")
        return ok(recorded=line)

    if effect in ("disable_agent", "deter_threat"):
        target, e = _nearby(world, agent, str(args.get("agent", "")).strip())
        if e:
            return err(e)
        assert target is not None
        reason = str(args.get("reason", "")).strip() or cap.motivation
        hours = cap.duration_hours if effect == "disable_agent" else min(cap.duration_hours, 1.0)
        target.disabled_until = time.time() + sim_hours_to_seconds(hours)
        target.disabled_by = agent.name
        world.log(
            f"🛑 {agent.name} used «{cap.display_name}» on {target.name} "
            f"for ~{hours:.1f} sim-hours: {reason[:100]}"
        )
        _mem_add(agent, f"Used {cap.display_name} on {target.name}: {reason}")
        return ok(
            target=target.name,
            restrainedHours=hours,
            untilSimHours=hours,
            reason=reason,
        )

    return err(f"Unhandled effect {effect}")


def _preview(text: str, limit: int = 80) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"
