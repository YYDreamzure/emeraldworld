"""Shared helpers for tool execution."""

from __future__ import annotations

import json
import math
from datetime import datetime
from typing import Any

from sim.landmarks import LANDMARKS, LANDMARK_BY_ID, LANDMARK_BY_NAME
from sim.singapore import NAME_ALIASES
from sim.world import AgentState, WorldState


def ok(**payload: Any) -> str:
    return json.dumps({"ok": True, **payload})


def err(message: str) -> str:
    return json.dumps({"error": message})


def resolve_place(place: str) -> str | None:
    key = place.strip().lower()
    if key in NAME_ALIASES:
        return NAME_ALIASES[key]
    if key in LANDMARK_BY_NAME:
        return LANDMARK_BY_NAME[key].id
    for lm in LANDMARKS:
        if lm.id.replace("_", " ") == key.replace("_", " "):
            return lm.id
        if lm.name.lower() == key:
            return lm.id
    return None


def require_location(agent: AgentState, *location_ids: str) -> str | None:
    if agent.location_id not in location_ids:
        names = ", ".join(LANDMARK_BY_ID[i].name for i in location_ids if i in LANDMARK_BY_ID)
        return err(f"Must be at {names}")
    return None


def require_home(world: WorldState, agent: AgentState) -> str | None:
    if not world.is_at_home(agent):
        return err("Must be at your HDB home")
    return None


def target_at_location(
    world: WorldState, agent: AgentState, target_name: str
) -> tuple[AgentState | None, str | None]:
    target = world.agents.get(target_name)
    if not target or not target.alive:
        return None, err(f"Unknown or deceased agent: {target_name}")
    if target.location_id != agent.location_id:
        return None, err(f"{target_name} is not at your location")
    return target, None


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def move_agent(world: WorldState, agent: AgentState, location_id: str, *, sprint: bool = False) -> str:
    from sim.justice import movement_blocked

    block = movement_blocked(agent, location_id)
    if block:
        return err(block)
    if world.data.is_burned(location_id):
        return err(f"{LANDMARK_BY_ID[location_id].name} is closed due to fire")
    agent.location_id = location_id
    world.sync_position(agent)
    follow = world.data.following.get(agent.name)
    if follow and follow in world.agents:
        leader = world.agents[follow]
        if leader.alive and leader.location_id == location_id:
            pass
    lm = world.location(agent)
    world.emit(
        "move",
        {
            "agent": agent.name,
            "x": agent.x,
            "z": agent.z,
            "location": lm.name,
            "sprint": sprint,
        },
    )
    return ok(location=lm.name, sprint=sprint)


def apply_followers(world: WorldState, leader: AgentState) -> None:
    for name, target in list(world.data.following.items()):
        if target != leader.name:
            continue
        follower = world.agents.get(name)
        if follower and follower.alive and follower.location_id != leader.location_id:
            if not world.data.is_burned(leader.location_id):
                follower.location_id = leader.location_id
                world.sync_position(follower)
