"""Automatic memory-graph updates from actions, speech, thoughts, and world events."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sim.memory_graph import ingest

if TYPE_CHECKING:
    from sim.history import ActionRecord, AgentWorldEvent
    from sim.world import AgentState, WorldState

_SKIP_KINDS = frozenset({"turn_start"})
_SOUL_TOOLS = frozenset({"add_to_soul", "refine_soul_belief"})
_LTM_TOOLS = frozenset(
    {
        "add_to_longterm_memory",
        "add_to_soul",
        "refine_soul_belief",
        "write_diary",
        "learn_personal_capability",
    }
)


def _observation_text(rec: ActionRecord) -> str:
    detail = (rec.detail or "").strip()
    if detail:
        return detail[:2000]
    summary = (rec.summary or "").strip()
    if rec.tool and summary:
        return f"[{rec.tool}] {summary}"[:2000]
    return summary[:2000]


def _tags_for_record(rec: ActionRecord) -> list[str]:
    tags: list[str] = []
    if rec.tool:
        tags.append(rec.tool)
    if rec.target:
        tags.append(rec.target)
    if rec.location:
        tags.append(rec.location)
    if rec.kind:
        tags.append(rec.kind)
    return tags[:8]


def _source_for_record(rec: ActionRecord) -> str:
    if rec.tool in _SOUL_TOOLS:
        return "soul"
    if rec.tool in _LTM_TOOLS:
        return "ltm"
    return "episodic"


def _protected_for_record(rec: ActionRecord) -> bool:
    if rec.tool in ("add_to_longterm_memory", "add_to_soul", "refine_soul_belief"):
        return True
    if rec.tool == "write_diary":
        return True
    return False


def observe_action(world: WorldState, rec: ActionRecord) -> None:
    """Mirror every recorded action into the acting agent's memory graph."""
    if rec.kind in _SKIP_KINDS:
        return
    agent = world.agents.get(rec.agent)
    if not agent or not agent.alive:
        return
    text = _observation_text(rec)
    if not text:
        return
    ingest(
        agent,
        text,
        protected=_protected_for_record(rec),
        source=_source_for_record(rec),
        tags=_tags_for_record(rec),
    )


def observe_event(world: WorldState, agent_name: str, event: AgentWorldEvent) -> None:
    """When an agent is notified of speech/crime/etc., store it in their brain."""
    agent = world.agents.get(agent_name)
    if not agent or not agent.alive:
        return
    if event.target == agent_name:
        line = f"{event.actor} → me: {event.detail[:500]}"
    else:
        line = f"Witnessed {event.actor}: {event.detail[:500]}"
    ingest(
        agent,
        f"[{event.kind}] {line}",
        source="episodic",
        tags=[event.actor, event.location_id, event.kind],
    )


def build_autonomy_briefing(world: WorldState, agent: AgentState) -> str:
    """Turn instructions: embodied agency, exploration, social interaction."""
    nearby = world.agents_at(agent.location_id, exclude=agent.name)
    nearby_names = ", ".join(a.name for a in nearby) or "none"
    lm = world.location(agent)
    todos = agent.todos[:5]
    todo_block = "\n".join(f"- {t}" for t in todos) if todos else "- (none — add goals with add_todo)"

    last_loc = agent.last_location_name
    moved = (
        f"You were last at {last_loc}; now at {lm.name}."
        if last_loc and last_loc != lm.name
        else f"You are at {lm.name}."
    )

    return f"""
## Autonomous agency (you are embodied — not a chat assistant)
- You live in a persistent world. **Only tool calls change state** — prose and Python fences do nothing.
- Each turn, act like a citizen: **observe → decide → act → remember**, then `set_mood_and_terminate`.
- Use at least one real tool call before `set_mood_and_terminate` (e.g. `get_nearby`, `go_to_place`, `think_aloud`, `say_to_agent`).
- **Explore:** use `list_landmarks` / `go_to_place` to visit new places; do not stay idle every round.
- **Socialize:** if agents are co-located (`get_nearby`), use `say_to_agent` for real conversation; use `send_message` only from afar.
- **Reflect:** use `think_aloud` for private reasoning; important facts → `add_to_longterm_memory`.
- Your **memory graph updates automatically** from everything you do, hear, and witness — use past brain context in decisions.
{moved}
- **Nearby agents:** {nearby_names}
- **Your todos:** 
{todo_block}
"""


def since_last_turn_digest(world: WorldState, agent_name: str, limit: int = 6) -> str:
    """Recent actions by this agent since previous turn_start."""
    acts = world.history._actions_since_previous_turn(agent_name, limit)
    if not acts:
        return "- (first actions this session)"
    lines = []
    for a in acts:
        text = _observation_text(a)
        loc = f" @ {a.location}" if a.location else ""
        mark = " ✗" if not a.ok else ""
        lines.append(f"- Tick {a.tick}{loc}{mark}: {text[:240]}")
    return "\n".join(lines)


def summarize_turn_to_brain(world: WorldState, agent: AgentState, *, limit: int = 12) -> str:
    """Deterministic turn summary ingested into the agent's memory graph.

    This is intentionally non-LLM: it compresses the last N action records from this turn.
    """
    acts = world.history._actions_since_previous_turn(agent.name, limit)
    if not acts:
        return ""
    loc = world.location(agent).name
    tools: list[str] = []
    targets: list[str] = []
    fails = 0
    for a in acts:
        if not a.ok:
            fails += 1
        if a.tool and a.tool not in tools and a.tool != "set_mood_and_terminate":
            tools.append(a.tool)
        if a.target and a.target not in targets:
            targets.append(a.target)
        # Heuristic: say_to_agent / messages often don't populate target consistently
        if a.args and a.tool in ("say_to_agent", "send_message", "call_agent", "whisper_to_agent"):
            t = str(a.args.get("agent", "")).strip()
            if t and t not in targets:
                targets.append(t)
    tools_txt = ", ".join(tools[:8]) or "(none)"
    tgt_txt = ", ".join(targets[:6]) or "(none)"
    fail_txt = f"; {fails} failed" if fails else ""
    mood = (agent.mood or "neutral")[:40]
    summary = (
        f"Turn summary @ {loc}: tools={tools_txt}; interacted={tgt_txt}; mood={mood}{fail_txt}."
    )
    ingest(agent, summary, source="episodic", tags=["turn_summary", agent.name, loc])
    return summary
