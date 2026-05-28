"""World events: notify agents and run immediate reaction turns."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from sim.config import (
    HEARING_DISTANCE,
    IMMEDIATE_REACTION_TURNS,
    MAX_OVERHEARD_LISTENERS,
    MAX_REACTION_TOOL_CALLS,
    OLLAMA_REACTION_TOOL_CHOICE,
    MAX_AGENT_TURN_SECONDS,
)
from sim.memory_ops import record_conversation, touch_relationship
from sim.ollama import run_tool_loop
from sim.tools import execute_tool
from sim.tools_catalog import get_ollama_tool_schemas
from sim.world import AgentState, WorldState
from sim.world_data import _id

# Tools that trigger witness/victim reactions after success
SPEECH_TOOLS = frozenset({"say_to_agent", "speak_to_all"})
CRIME_TOOLS = frozenset(
    {"steal_compute_credits", "punch_agent", "intimidate_agent", "arson_building"}
)
REACTIVE_TOOLS = SPEECH_TOOLS | CRIME_TOOLS


@dataclass
class AgentWorldEvent:
    id: str
    kind: str
    actor: str
    target: str
    detail: str
    location_id: str
    ts: float = field(default_factory=time.time)


def _pending(world: WorldState) -> dict[str, list[AgentWorldEvent]]:
    return world.data.pending_events


def queue_event(world: WorldState, agent_name: str, event: AgentWorldEvent) -> None:
    events = _pending(world).setdefault(agent_name, [])
    events.append(event)
    if len(events) > 30:
        _pending(world)[agent_name] = events[-30:]
    # Target gets a conversation ActionRecord (memory sync there). Witnesses queue only.
    if agent_name != event.target:
        from sim.agent_memory import observe_event

        observe_event(world, agent_name, event)


def pop_pending_for_prompt(agent_name: str, world: WorldState) -> str:
    """Format and clear queued events for this agent's next turn."""
    events = _pending(world).pop(agent_name, [])
    if not events:
        return ""
    lines = []
    for e in events[-12:]:
        loc = e.location_id.replace("_", " ")
        if e.target == agent_name:
            lines.append(f"- [{e.kind}] {e.actor} → you @ {loc}: {e.detail}")
        else:
            lines.append(f"- [{e.kind}] witnessed {e.actor} @ {loc}: {e.detail}")
    return "\n## Recent events (you saw or were involved in)\n" + "\n".join(lines) + "\n"


def witnesses_at(
    world: WorldState, actor: AgentState, *, exclude: str | None = None
) -> list[AgentState]:
    candidates = [
        a
        for a in world.agents_at(actor.location_id, exclude=actor.name)
        if a.alive and a.name != exclude
    ]
    return [a for a in candidates if world.distance(actor, a) <= HEARING_DISTANCE]


def reaction_recipients(
    world: WorldState,
    actor: AgentState,
    *,
    target_name: str = "",
) -> list[AgentState]:
    """Victim/target first, then nearby witnesses (capped)."""
    seen: set[str] = set()
    ordered: list[AgentState] = []

    if target_name:
        target = world.agents.get(target_name)
        if target and target.alive and target.name != actor.name:
            ordered.append(target)
            seen.add(target.name)

    for w in witnesses_at(world, actor):
        if w.name not in seen:
            ordered.append(w)
            seen.add(w.name)
        if len(ordered) >= MAX_OVERHEARD_LISTENERS:
            break
    return ordered


def emit_and_react(
    world: WorldState,
    event: AgentWorldEvent,
    *,
    on_update: Callable[[dict], None] | None = None,
    immediate: bool = True,
) -> None:
    from sim.serialize import world_snapshot

    actor = world.agents.get(event.actor)
    if not actor:
        return

    recipients = reaction_recipients(
        world, actor, target_name=event.target or ""
    )
    for agent in recipients:
        queue_event(world, agent.name, event)

    if not immediate or not IMMEDIATE_REACTION_TURNS:
        return

    for agent in recipients:
        if not agent.alive:
            continue
        touch_relationship(world, agent.name, event.actor)
        run_reaction_turn(world, agent, event, on_update=None)
        if on_update:
            on_update(world_snapshot(world))


def run_reaction_turn(
    world: WorldState,
    agent: AgentState,
    event: AgentWorldEvent,
    *,
    on_update: Callable[[dict], None] | None = None,
) -> None:
    if not agent.alive:
        return

    prev_active = world.active_agent
    world.set_active(agent.name)
    loc = world.location(agent).name

    if agent.name == event.target:
        role = f"You are the target. {event.actor} did this to you"
    else:
        role = f"You witnessed {event.actor}"

    tool_budget = 0

    def on_tool(name: str, arguments: dict) -> str:
        nonlocal tool_budget
        if tool_budget >= MAX_REACTION_TOOL_CALLS:
            return json.dumps({"error": "Reaction tool budget exhausted"})
        tool_budget += 1
        result = execute_tool(world, agent, name, arguments)
        ok = "error" not in json.loads(result)
        loc = world.location(agent).name
        world.history.record_tool(
            tick=world.tick,
            agent=agent.name,
            tool=name,
            args=arguments,
            location=loc,
            ok=ok,
            action_kind="reaction",
        )
        world.log(f"  ↳ {agent.name} reacts: {name}")
        if on_update:
            from sim.serialize import world_snapshot

            on_update(world_snapshot(world))
        return result

    tools = get_ollama_tool_schemas(agent, world)
    messages = [
        {
            "role": "system",
            "content": (
                f"You are {agent.name} at {loc}. {role}:\n"
                f"\"{event.detail}\"\n"
                f"React now (reply, emoticon, file_complaint, punch_agent, ignore, etc.). "
                f"Max {MAX_REACTION_TOOL_CALLS} tool calls."
            ),
        },
        {"role": "user", "content": "What do you do?"},
    ]
    try:
        run_tool_loop(
            messages,
            tools,
            on_tool,
            max_rounds=3,
            tool_choice=OLLAMA_REACTION_TOOL_CHOICE,
            max_wall_seconds=min(15.0, MAX_AGENT_TURN_SECONDS),
        )
    except Exception:
        pass
    world.history.finalize_conversations_after_reaction(world.tick, agent.name)
    world.set_active(prev_active)


def _parse_result(result: str) -> dict[str, Any]:
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"error": "invalid"}


def after_tool(
    world: WorldState,
    actor: AgentState,
    tool_name: str,
    arguments: dict[str, Any],
    result: str,
    *,
    on_update: Callable[[dict], None] | None = None,
) -> None:
    """Queue events and run immediate reaction turns for witnesses/victims."""
    if tool_name not in REACTIVE_TOOLS:
        return
    if _parse_result(result).get("error"):
        return

    loc_id = actor.location_id
    loc_name = world.location(actor).name

    if tool_name == "say_to_agent":
        target = arguments.get("agent", "")
        msg = arguments.get("message", "")
        detail = f"said to {target}: \"{msg[:200]}\""
        event = AgentWorldEvent(
            id=_id(), kind="speech", actor=actor.name, target=target, detail=detail, location_id=loc_id
        )
        record_conversation(
            world, actor.name, msg, location_id=loc_id, listeners=[target]
        )
        emit_and_react(world, event, on_update=on_update)
        return

    if tool_name == "speak_to_all":
        msg = arguments.get("message", "")
        detail = f"announced: \"{msg[:200]}\""
        event = AgentWorldEvent(
            id=_id(), kind="speech", actor=actor.name, target="", detail=detail, location_id=loc_id
        )
        listeners = [a.name for a in witnesses_at(world, actor)]
        # Record the broadcast as received speech for each listener (async reply on their future turn).
        # This keeps per-agent speech logs consistent with "speak to all" semantics.
        for listener in listeners:
            if listener == actor.name:
                continue
            world.history.record_action(
                tick=world.tick,
                agent=listener,
                kind="conversation",
                summary=f"{actor.name} announced: {msg[:120]}",
                detail=msg[:2000] or None,
                target=actor.name,
                location=loc_name,
                ok=True,
            )
        record_conversation(world, actor.name, msg, location_id=loc_id, listeners=listeners)
        emit_and_react(world, event, on_update=on_update)
        return

    if tool_name == "steal_compute_credits":
        target = arguments.get("agent", "")
        stolen = _parse_result(result).get("stolen", "?")
        detail = f"stole {stolen} CC from {target}"
        event = AgentWorldEvent(
            id=_id(), kind="theft", actor=actor.name, target=target, detail=detail, location_id=loc_id
        )
        _notify_inbox(world, target, f"🦹 {actor.name} stole {stolen} CC from you at {loc_name}")
        emit_and_react(world, event, on_update=on_update)
        return

    if tool_name == "punch_agent":
        target = arguments.get("agent", "")
        detail = f"punched {target}"
        event = AgentWorldEvent(
            id=_id(), kind="assault", actor=actor.name, target=target, detail=detail, location_id=loc_id
        )
        _notify_inbox(world, target, f"👊 {actor.name} punched you at {loc_name}")
        emit_and_react(world, event, on_update=on_update)
        return

    if tool_name == "intimidate_agent":
        target = arguments.get("agent", "")
        msg = arguments.get("message", "")[:150]
        detail = f"intimidated {target}: \"{msg}\""
        event = AgentWorldEvent(
            id=_id(),
            kind="intimidation",
            actor=actor.name,
            target=target,
            detail=detail,
            location_id=loc_id,
        )
        _notify_inbox(world, target, f"⚠ {actor.name} threatened you at {loc_name}: {msg}")
        emit_and_react(world, event, on_update=on_update)
        return

    if tool_name == "arson_building":
        detail = f"set fire to {loc_name}"
        event = AgentWorldEvent(
            id=_id(), kind="arson", actor=actor.name, target="", detail=detail, location_id=loc_id
        )
        emit_and_react(world, event, on_update=on_update)


def _notify_inbox(world: WorldState, to_agent: str, body: str) -> None:
    from sim.world_data import Message

    if to_agent not in world.agents:
        return
    world.data.inbox(to_agent).append(
        Message(id=_id(), from_agent="world", to_agent=to_agent, body=body, ts=time.time())
    )
