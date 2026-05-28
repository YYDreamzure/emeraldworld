import json
import re
import time
from typing import Callable

from sim.config import (
    BROADCAST_ON_EVERY_TOOL,
    EXECUTE_PLANNED_TOOLS,
    MAX_AGENT_TURN_SECONDS,
    MAX_PLANNED_TOOLS_PER_TURN,
    MAX_TOOL_CALLS_PER_TURN,
    MAX_TURN_RECOVERY_LOOPS,
    MIN_TURN_ACTIONS,
)
from sim.activity import window_summary
from sim.health import update_health
from sim.needs import apply_agent_needs_decay, needs_summary
from sim.ollama import run_tool_loop
from sim.prompts import build_system_prompt, build_user_prompt
from sim import events
from sim.serialize import world_snapshot
from sim.tools import execute_tool
from sim.tools_catalog import get_ollama_tool_schemas
from sim.history import _preview
from sim.weather_sync import fetch_weather
from sim.world import AgentState, WorldState

_FAKE_TOOL_PATTERN = re.compile(
    r"\b(write_diary|write_blog|update_blog|recharge_energy|set_mood_and_terminate|"
    r"go_to_place|think_aloud|say_to_agent)\s*\(",
    re.IGNORECASE,
)


def _assistant_text(msg: dict) -> str:
    return (msg.get("content") or "").strip()


def _unexecuted_plan_from_history(history: list[dict]) -> str:
    """Find the longest assistant prose that looks like a fake tool plan."""
    candidates: list[str] = []
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        text = _assistant_text(msg)
        if not text or text.startswith("{"):
            continue
        if _looks_like_unexecuted_tool_plan(text):
            candidates.append(text)
    if candidates:
        return max(candidates, key=len)
    for msg in reversed(history):
        if msg.get("role") == "assistant":
            text = _assistant_text(msg)
            if text and not text.startswith("{"):
                return text
    return ""


def _looks_like_unexecuted_tool_plan(content: str) -> bool:
    if not content:
        return False
    lower = content.lower()
    if "```" in content:
        return True
    if "tools used:" in lower or "**action plan:**" in lower:
        return True
    return _FAKE_TOOL_PATTERN.search(content) is not None


def _counts_as_turn_action(tool_name: str) -> bool:
    return tool_name not in ("set_mood_and_terminate", "ignore")


def run_agent_turn(
    world: WorldState,
    agent: AgentState,
    *,
    on_update: Callable[[dict], None] | None = None,
    max_tool_calls: int = MAX_TOOL_CALLS_PER_TURN,
    turn_kind: str = "regular",
) -> None:
    def broadcast() -> None:
        if on_update:
            on_update(world_snapshot(world))

    turn_started_at = time.time()
    from sim.justice import enforce_custody
    from sim.personal_capabilities import clear_expired_status

    for a in world.agents.values():
        if a.alive:
            enforce_custody(world, a)
            clear_expired_status(a, world)
            update_health(a)
    agent.terminated = False
    agent.gesture = None
    tool_calls = 0
    world.data.turn_action_counts[agent.name] = 0
    loc_name = world.location(agent).name
    world.set_active(agent.name)
    world.clear_speeches()
    world.history.start_turn(world.tick, agent.name, loc_name)
    broadcast()

    def on_tool_call(name: str, arguments: dict) -> str:
        nonlocal tool_calls
        if agent.terminated and name != "set_mood_and_terminate":
            return json.dumps({"error": "Turn already terminated"})
        if tool_calls >= max_tool_calls:
            return json.dumps({"error": "Tool call budget exhausted for this turn"})
        tool_calls += 1
        if _counts_as_turn_action(name):
            world.data.turn_action_counts[agent.name] = (
                world.data.turn_action_counts.get(agent.name, 0) + 1
            )
        result = execute_tool(world, agent, name, arguments)
        if agent.alive:
            events.after_tool(
                world,
                agent,
                name,
                arguments,
                result,
                on_update=on_update,
            )
        ok = "error" not in json.loads(result)
        if not agent.alive:
            if BROADCAST_ON_EVERY_TOOL:
                broadcast()
            return result
        world.history.record_tool(
            tick=world.tick,
            agent=agent.name,
            tool=name,
            args=arguments,
            location=world.location(agent).name,
            ok=ok,
        )
        world.log(f"  {agent.name}: {name}")
        world.emit("tool", {"agent": agent.name, "tool": name, "args": arguments})
        # Always broadcast after each tool so the UI updates live.
        broadcast()
        return result

    from sim.vitality import energy_status, hours_until_death

    status = energy_status(agent)
    death_warn = ""
    if status == "critical":
        hrs = hours_until_death(agent)
        death_warn = (
            f" URGENT: 0% energy — you die in ~{hrs:.1f}h if you do not recharge at home or Maxwell."
        )

    event_context = events.pop_pending_for_prompt(agent.name, world)

    messages = [
        {"role": "system", "content": build_system_prompt(agent, world)},
        {
            "role": "user",
            "content": build_user_prompt(agent)
            + event_context
            + death_warn
            + f"\n\nNeeds: {needs_summary(agent)}. Turn type: {turn_kind}.",
        },
    ]

    world.log(f"Turn: {agent.name} @ {loc_name} ({needs_summary(agent)})")
    tools = get_ollama_tool_schemas(agent, world)
    history = run_tool_loop(
        messages,
        tools,
        on_tool_call,
        max_wall_seconds=MAX_AGENT_TURN_SECONDS,
        should_stop=lambda: agent.terminated or (not agent.alive),
    )

    def execute_planned_from_history() -> int:
        if not EXECUTE_PLANNED_TOOLS:
            return 0
        from sim.tool_salvage import execute_planned_tool_calls_from_history

        return execute_planned_tool_calls_from_history(
            history,
            on_tool_call,
            max_calls=MAX_PLANNED_TOOLS_PER_TURN,
            log=world.log,
        )

    execute_planned_from_history()

    for _ in range(max(0, MAX_TURN_RECOVERY_LOOPS)):
        actions = world.data.turn_action_counts.get(agent.name, 0)
        if (
            tool_calls > 0
            and actions >= MIN_TURN_ACTIONS
            or not agent.alive
            or agent.terminated
        ):
            break
        if tool_calls == 0:
            msg = (
                "ERROR: Zero native tool_calls executed. You MUST invoke tools through the API "
                "(get_nearby, think_aloud, go_to_place, write_diary, etc.) then set_mood_and_terminate. "
                "Prose plans, ```python blocks, and XML tags are not reliable — use tool_calls only."
            )
        else:
            msg = (
                f"ERROR: Need at least {MIN_TURN_ACTIONS} action(s) before set_mood_and_terminate "
                f"(you have {actions}). Use get_nearby or think_aloud, then end turn."
            )
        history.append({"role": "user", "content": msg})
        history = run_tool_loop(
            history,
            tools,
            on_tool_call,
            max_wall_seconds=MAX_AGENT_TURN_SECONDS,
            should_stop=lambda: agent.terminated or (not agent.alive),
        )
        execute_planned_from_history()

    if not agent.alive:
        world.set_active(None)
        broadcast()
        return

    final = history[-1] if history else {}
    content = _assistant_text(final)
    if tool_calls == 0:
        plan_text = _unexecuted_plan_from_history(history)
        if plan_text:
            world.log(
                f"{agent.name}: (turn ended with no tool calls — plan text not executed)"
            )
            preview = plan_text[:240] + ("…" if len(plan_text) > 240 else "")
            world.log(f"  📋 Unexecuted plan: {preview}")
            world.history.record_action(
                tick=world.tick,
                agent=agent.name,
                kind="plan",
                summary="Unexecuted turn plan (no tools ran — check native tool_calls or fenced JSON)",
                detail=plan_text,
                tool="unexecuted_plan",
                location=world.location(agent).name,
            )
        elif content and not content.startswith("{"):
            world.log(f"{agent.name}: {content[:500]}")
            world.set_speech(agent, content)
            world.history.record_action(
                tick=world.tick,
                agent=agent.name,
                kind="speech",
                summary=_preview(content),
                detail=content,
                location=world.location(agent).name,
            )
    elif content and not content.startswith("{"):
        world.log(f"{agent.name}: {content[:500]}")
        world.set_speech(agent, content)
        world.history.record_action(
            tick=world.tick,
            agent=agent.name,
            kind="speech",
            summary=_preview(content),
            detail=content,
            location=world.location(agent).name,
        )

    # Compulsory termination: ensure set_mood_and_terminate is invoked as a tool call.
    # If the model didn't call it, we invoke it with a safe default mood.
    if not agent.terminated:
        mood = agent.mood or "neutral"
        try:
            forced = on_tool_call("set_mood_and_terminate", {"mood": mood})
            if "error" in json.loads(forced):
                # Fallback: do not stall the sim forever if the forced tool call is rejected.
                agent.mood = mood
                agent.terminated = True
        except Exception:
            agent.mood = mood
            agent.terminated = True

    agent.last_location_name = loc_name
    world.history.complete_turn(world.tick, agent.name, agent.mood)
    for ev in world.history.events:
        if ev.kind in ("travel", "conversation") and ev.status == "ongoing":
            if ev.agents == [agent.name] or agent.name in ev.agents:
                ev.status = "completed"
                ev.ended_tick = world.tick
                ev.ended_ts = time.time()

    if agent.alive:
        turn_dt = time.time() - turn_started_at
        # Programmatic brain update: summarize this turn into the associative memory graph.
        from sim.agent_memory import summarize_turn_to_brain
        from sim.memory_graph import apply_decay

        summarize_turn_to_brain(world, agent)
        apply_decay(agent, turn_dt)
        if apply_agent_needs_decay(world, agent, dt=turn_dt):
            world.set_active(None)
            broadcast()
            return

    world.tick += 1
    world.set_active(None)
    broadcast()


def refresh_weather(world: WorldState) -> None:
    text = fetch_weather()
    world.data.weather = text
    world.data.weather_history.append({"weather": text, "ts": time.time()})
    if len(world.data.weather_history) > 200:
        world.data.weather_history = world.data.weather_history[-200:]
