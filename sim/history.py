"""Per-agent action history and world event tracking for the dashboard."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4


def _id() -> str:
    return uuid4().hex[:10]


def _preview(text: str, limit: int = 100) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def _tool_detail(tool: str, args: dict[str, Any]) -> str | None:
    if tool == "say_to_agent":
        return str(args.get("message", "")).strip() or None
    if tool == "speak_to_all":
        return str(args.get("message", "")).strip() or None
    if tool == "think_aloud":
        return str(args.get("thought", "")).strip() or None
    if tool == "add_to_longterm_memory":
        return str(args.get("memory", "")).strip() or None
    if tool == "add_todo":
        return str(args.get("task", "")).strip() or None
    if tool in ("submit_removal_proposal", "submit_townhall_proposal"):
        return str(args.get("reason", args.get("description", ""))).strip() or None
    if tool == "write_blog":
        return str(args.get("content", "")).strip() or None
    if tool == "add_to_billboard":
        return str(args.get("content", "")).strip() or None
    return None


def _tool_summary(tool: str, args: dict[str, Any]) -> str:
    if tool == "go_to_place":
        return f"Walked to {args.get('place', '?')}"
    if tool == "say_to_agent":
        msg = str(args.get("message", ""))
        return f"Said to {args.get('agent', '?')}: {_preview(msg)}"
    if tool == "speak_to_all":
        msg = str(args.get("message", ""))
        return f"Announced: {_preview(msg)}"
    if tool == "think_aloud":
        thought = str(args.get("thought", "")).strip()
        return f"Thought: {thought}" if thought else "Thought"
    if tool == "show_emoticon":
        return f"Reacted {args.get('emoticon', '')}"
    if tool == "add_to_longterm_memory":
        return f"Remembered: {_preview(str(args.get('memory', '')))}"
    if tool == "refine_soul_belief":
        return f"Refined soul belief #{args.get('index', '?')}"
    if tool == "view_memory_brain":
        return "Inspected memory brain graph"
    if tool == "rehearse_memory":
        return f"Rehearsed memory {args.get('memory_id', '?')}"
    if tool == "add_todo":
        return f"Added todo: {_preview(str(args.get('task', '')))}"
    if tool == "set_mood_and_terminate":
        return f"Ended turn (mood: {args.get('mood', 'neutral')})"
    if tool == "recharge_energy":
        return "Recharged energy"
    if tool == "go_home":
        return "Returned home"
    if tool == "submit_removal_proposal":
        return f"Proposed removing {args.get('agent', '?')}"
    if tool == "vote_on_proposal":
        return f"Voted {args.get('vote', '?')} on {args.get('proposal_id', '?')}"
    if tool == "list_proposals":
        return "Listed Town Hall proposals"
    if tool == "investigate_event_log":
        return "Reviewed world event log for crimes"
    if tool == "file_enforcement_proposal":
        target = args.get("target", "?")
        return f"Filed enforcement case vs {target} at Tanglin Police"
    if tool == "list_community_complaints":
        return "Listed community complaints"
    if tool == "list_enforcement_cases":
        return "Listed Supreme Court enforcement cases"
    if tool == "read_enforcement_case":
        return f"Reviewed case {args.get('case_id', '?')}"
    if tool == "summon_defendant_to_court":
        return f"Summoned defendant for case {args.get('case_id', '?')}"
    if tool == "pass_judgment":
        return f"Passed judgment ({args.get('sentence_type', '?')}) on case {args.get('case_id', '?')}"
    if tool == "check_crime_in_singapore_law":
        return f"Checked law coverage for {args.get('crime_type', '?')}"
    if tool == "propose_singapore_law":
        return f"Proposed new Singapore law for {args.get('crime_type', '?')}"
    if tool == "list_singapore_law_amendments":
        return "Listed adopted Singapore law amendments"
    if tool == "perform_community_service":
        return f"Community service shift ({args.get('hours', '?')}h)"
    if tool == "learn_personal_capability":
        return f"Learned personal tool: {args.get('name', '?')}"
    if tool == "list_personal_capabilities":
        return "Listed personal capabilities"
    if tool.startswith("cap_"):
        return f"Used personal capability on {args.get('agent', '?')}"
    if tool == "call_agent":
        return f"Called {args.get('agent', '?')}"
    if tool in ("visit_hospital", "seek_hospital_treatment"):
        return "Sought treatment at NUH"
    if tool == "file_covert_security_referral":
        return f"Covert referral vs {args.get('target', '?')}"
    if tool in ("list_landmarks", "list_agents", "get_nearby", "list_todo"):
        return f"Checked {tool.replace('_', ' ')}"
    return tool.replace("_", " ")


SPEECH_TOOLS = frozenset(
    {
        "say_to_agent",
        "speak_to_all",
        "whisper_to_agent",
        "send_message",
        "call_agent",
    }
)


_FULL_TEXT_ARG_KEYS = frozenset({"thought", "message", "memory", "incident", "content"})

def _safe_args(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, val in args.items():
        if isinstance(val, (str, int, float, bool)):
            if isinstance(val, str):
                if key in _FULL_TEXT_ARG_KEYS:
                    out[key] = val[:16000]
                else:
                    out[key] = val[:200]
            else:
                out[key] = val
    return out


def action_full_text(a: ActionRecord) -> str:
    """Complete text for UI feeds — never abbreviated."""
    args = a.args or {}
    if a.tool == "think_aloud":
        body = args.get("thought") or args.get("content") or a.detail or ""
        text = str(body).strip()
    elif a.kind == "plan" or a.tool == "unexecuted_plan":
        text = (a.detail or a.summary or "").strip()
    else:
        text = (a.detail or "").strip()
        if not text:
            text = (a.summary or "").strip()
            if text.lower().startswith("thought:"):
                text = text[9:].strip()
    return text[:16000]


@dataclass
class ActionRecord:
    id: str
    tick: int
    ts: float
    agent: str
    kind: str
    summary: str
    detail: str | None = None
    tool: str | None = None
    location: str | None = None
    target: str | None = None
    args: dict[str, Any] = field(default_factory=dict)
    ok: bool = True


@dataclass
class WorldEvent:
    id: str
    tick: int
    ts: float
    status: str  # ongoing | completed
    kind: str
    title: str
    summary: str
    agents: list[str] = field(default_factory=list)
    ended_tick: int | None = None
    ended_ts: float | None = None
    last_speaker: str | None = None


class HistoryTracker:
    MAX_ACTIONS = 400
    MAX_EVENTS = 80
    MAX_PER_AGENT = 50

    def __init__(self) -> None:
        self.actions: list[ActionRecord] = []
        self.events: list[WorldEvent] = []
        self._ongoing_turn: WorldEvent | None = None
        self._agent_tools: dict[str, set[str]] = {name: set() for name in []}
        self._agent_locations: dict[str, set[str]] = {name: set() for name in []}
        self._world: Any = None

    def attach(self, world: Any) -> None:
        """Bind world so actions auto-sync to agent memory graphs."""
        self._world = world

    def _ensure_agent(self, name: str) -> None:
        if name not in self._agent_tools:
            self._agent_tools[name] = set()
            self._agent_locations[name] = set()

    def record_action(
        self,
        *,
        tick: int,
        agent: str,
        kind: str,
        summary: str,
        tool: str | None = None,
        location: str | None = None,
        target: str | None = None,
        detail: str | None = None,
        args: dict | None = None,
        ok: bool = True,
    ) -> ActionRecord:
        self._ensure_agent(agent)
        rec = ActionRecord(
            id=_id(),
            tick=tick,
            ts=time.time(),
            agent=agent,
            kind=kind,
            summary=summary,
            detail=detail,
            tool=tool,
            location=location,
            target=target,
            args=args or {},
            ok=ok,
        )
        self.actions.append(rec)
        if len(self.actions) > self.MAX_ACTIONS:
            self.actions = self.actions[-self.MAX_ACTIONS :]
        if tool:
            self._agent_tools[agent].add(tool)
        if location:
            self._agent_locations[agent].add(location)
        if self._world is not None:
            from sim.config import SYNC_ACTIONS_TO_MEMORY

            if SYNC_ACTIONS_TO_MEMORY and rec.kind not in ("turn_start",):
                from sim.agent_memory import observe_action

                observe_action(self._world, rec)
        return rec

    def record_say_to_agent(
        self,
        *,
        tick: int,
        speaker: str,
        target: str,
        message: str,
        location: str,
        ok: bool = True,
        action_kind: str = "tool",
    ) -> ActionRecord:
        """Persist speech on the speaker dashboard.

        Delivery to the listener is asynchronous: they see it via queued events on their next turn,
        and they only "reply" when they later choose a speech tool themselves.
        """
        msg = (message or "").strip()
        rec = self.record_action(
            tick=tick,
            agent=speaker,
            kind=action_kind,
            summary=f"Said to {target}: {_preview(msg)}",
            detail=msg or None,
            tool="say_to_agent",
            location=location,
            target=target,
            args={"agent": target, "message": msg},
            ok=ok,
        )
        if target:
            self._maybe_conversation_event(tick, speaker, target, msg)
        return rec

    def record_tool(
        self,
        *,
        tick: int,
        agent: str,
        tool: str,
        args: dict,
        location: str,
        ok: bool = True,
        action_kind: str = "tool",
    ) -> ActionRecord:
        if tool == "say_to_agent":
            return self.record_say_to_agent(
                tick=tick,
                speaker=agent,
                target=str(args.get("agent", "")),
                message=str(args.get("message", "")),
                location=location,
                ok=ok,
                action_kind=action_kind,
            )

        target = args.get("agent") if tool in ("whisper_to_agent",) else None
        kind = action_kind
        if tool == "think_aloud":
            kind = "thought"
        rec = self.record_action(
            tick=tick,
            agent=agent,
            kind=kind,
            summary=_tool_summary(tool, args),
            detail=_tool_detail(tool, args),
            tool=tool,
            location=location,
            target=target,
            args=args,
            ok=ok,
        )
        if tool == "go_to_place":
            self._maybe_travel_event(tick, agent, args.get("place", ""))
        return rec

    def start_turn(self, tick: int, agent: str, location: str) -> None:
        if self._ongoing_turn:
            self.complete_turn(tick)
        self._ongoing_turn = WorldEvent(
            id=_id(),
            tick=tick,
            ts=time.time(),
            status="ongoing",
            kind="turn",
            title=f"{agent}'s turn",
            summary=f"Acting at {location}",
            agents=[agent],
        )
        self.events.append(self._ongoing_turn)
        self.record_action(
            tick=tick,
            agent=agent,
            kind="turn_start",
            summary=f"Started turn at {location}",
            location=location,
        )

    def complete_turn(self, tick: int, agent: str | None = None, mood: str = "neutral") -> None:
        if agent:
            self._complete_one_sided_conversations(tick, agent)
        if not self._ongoing_turn:
            return
        ev = self._ongoing_turn
        ev.status = "completed"
        ev.ended_tick = tick
        ev.ended_ts = time.time()
        if agent:
            ev.summary = f"Finished at {mood} mood"
        self._ongoing_turn = None
        if len(self.events) > self.MAX_EVENTS:
            self.events = self.events[-self.MAX_EVENTS :]

    def _finish_event(self, ev: WorldEvent, tick: int) -> None:
        ev.status = "completed"
        ev.ended_tick = tick
        ev.ended_ts = time.time()

    def _complete_one_sided_conversations(self, tick: int, agent: str) -> None:
        """Close conversations where this agent spoke last and no reply followed."""
        for ev in self.events:
            if (
                ev.kind == "conversation"
                and ev.status == "ongoing"
                and ev.last_speaker == agent
                and agent in ev.agents
            ):
                self._finish_event(ev, tick)

    def finalize_conversations_after_reaction(self, tick: int, listener: str) -> None:
        """After a reaction turn, close threads where the listener did not reply."""
        for ev in self.events:
            if (
                ev.kind == "conversation"
                and ev.status == "ongoing"
                and listener in ev.agents
                and ev.last_speaker
                and ev.last_speaker != listener
            ):
                self._finish_event(ev, tick)

    def _maybe_conversation_event(
        self, tick: int, speaker: str, target: str, message: str
    ) -> None:
        pair = {speaker, target}
        line = f"{speaker}: {message}"
        for ev in reversed(self.events[-12:]):
            if (
                ev.status == "ongoing"
                and ev.kind == "conversation"
                and set(ev.agents) == pair
            ):
                if ev.last_speaker and ev.last_speaker != speaker:
                    ev.summary = f"{ev.summary} · {line}"
                    self._finish_event(ev, tick)
                else:
                    ev.summary = line
                ev.last_speaker = speaker
                self._complete_stale_conversations(tick, except_id=ev.id)
                return
        self.events.append(
            WorldEvent(
                id=_id(),
                tick=tick,
                ts=time.time(),
                status="ongoing",
                kind="conversation",
                title=f"{speaker} ↔ {target}",
                summary=line,
                agents=[speaker, target],
                last_speaker=speaker,
            )
        )
        self._complete_stale_conversations(tick, except_id=self.events[-1].id)

    def _complete_stale_conversations(self, tick: int, except_id: str) -> None:
        now = time.time()
        for ev in self.events:
            if (
                ev.kind == "conversation"
                and ev.status == "ongoing"
                and ev.id != except_id
                and now - ev.ts > 120
            ):
                ev.status = "completed"
                ev.ended_tick = tick
                ev.ended_ts = now

    def _maybe_travel_event(self, tick: int, agent: str, place: str) -> None:
        for ev in reversed(self.events[-5:]):
            if (
                ev.status == "ongoing"
                and ev.kind == "travel"
                and ev.agents == [agent]
            ):
                ev.summary = f"Traveling — now heading to {place}"
                return
        self.events.append(
            WorldEvent(
                id=_id(),
                tick=tick,
                ts=time.time(),
                status="ongoing",
                kind="travel",
                title=f"{agent} traveling",
                summary=f"Heading to {place}",
                agents=[agent],
            )
        )
        for ev in self.events:
            if (
                ev.kind == "travel"
                and ev.status == "ongoing"
                and ev.agents == [agent]
                and ev.id != self.events[-1].id
            ):
                ev.status = "completed"
                ev.ended_tick = tick
                ev.ended_ts = time.time()

    CRIME_TOOLS = frozenset(
        {
            "steal_compute_credits",
            "arson_building",
            "punch_agent",
            "intimidate_agent",
        }
    )

    def investigate_crimes(
        self,
        *,
        limit: int = 40,
        suspect: str | None = None,
        crime_type: str | None = None,
    ) -> list[dict]:
        """Structured event-log slice for law-enforcement review."""
        type_to_tool = {
            "theft": "steal_compute_credits",
            "arson": "arson_building",
            "intimidation": "intimidate_agent",
            "assault": "punch_agent",
        }
        tool_filter: set[str] | None = None
        if crime_type:
            key = crime_type.strip().lower()
            if key in type_to_tool:
                tool_filter = {type_to_tool[key]}
            elif key in self.CRIME_TOOLS:
                tool_filter = {key}
        rows: list[dict] = []
        for a in reversed(self.actions):
            if a.tool not in self.CRIME_TOOLS or not a.ok:
                continue
            if tool_filter and a.tool not in tool_filter:
                continue
            if suspect and a.agent != suspect and a.target != suspect:
                continue
            rows.append(
                {
                    "actionId": a.id,
                    "tick": a.tick,
                    "ts": a.ts,
                    "actor": a.agent,
                    "target": a.target or "",
                    "tool": a.tool,
                    "location": a.location or "",
                    "summary": a.summary,
                    "detail": a.detail,
                }
            )
            if len(rows) >= limit:
                break
        return rows

    def agent_actions(self, name: str, limit: int = 40) -> list[ActionRecord]:
        return [a for a in reversed(self.actions) if a.agent == name][:limit]

    @staticmethod
    def is_thought_record(a: ActionRecord, agent_name: str) -> bool:
        del agent_name  # thoughts are only this agent's inner voice
        if a.tool == "think_aloud":
            return True
        if a.kind in ("thought", "plan"):
            return True
        return False

    @staticmethod
    def is_speech_record(a: ActionRecord, agent_name: str) -> bool:
        if a.tool in SPEECH_TOOLS and a.agent == agent_name:
            return True
        if a.kind == "speech" and a.agent == agent_name:
            return True
        if a.kind == "conversation" and (
            a.target == agent_name or a.agent == agent_name
        ):
            return True
        return False

    def agent_thoughts(self, name: str, limit: int = 50) -> list[ActionRecord]:
        return [
            a
            for a in reversed(self.actions)
            if a.agent == name
            and self.is_thought_record(a, name)
            and a.kind != "plan"
        ][:limit]

    def agent_plan_log(self, name: str, limit: int = 30) -> list[ActionRecord]:
        return [
            a
            for a in reversed(self.actions)
            if a.agent == name and a.kind == "plan"
        ][:limit]

    def agent_speech_log(self, name: str, limit: int = 50) -> list[ActionRecord]:
        return [
            a
            for a in reversed(self.actions)
            if self.is_speech_record(a, name)
        ][:limit]

    def agent_tool_log(self, name: str, limit: int = 50) -> list[ActionRecord]:
        return [
            a
            for a in reversed(self.actions)
            if a.agent == name
            and a.tool
            and not self.is_thought_record(a, name)
            and not self.is_speech_record(a, name)
        ][:limit]

    def agent_action_log(self, name: str, limit: int = 50) -> list[ActionRecord]:
        thought_ids = {a.id for a in self.agent_thoughts(name, limit=200)}
        speech_ids = {a.id for a in self.agent_speech_log(name, limit=200)}
        exclude = thought_ids | speech_ids
        return [
            a
            for a in reversed(self.actions)
            if a.agent == name
            and a.id not in exclude
            and a.kind != "turn_start"
        ][:limit]

    def agent_events(self, name: str, limit: int = 20) -> list[WorldEvent]:
        return [e for e in reversed(self.events) if name in e.agents][:limit]

    def prompt_action_recap(self, name: str, limit: int = 8) -> str:
        """Bullet lines of this agent's recent actions for the system prompt."""
        acts = self._actions_since_previous_turn(name, limit)
        if not acts:
            return "- (none yet)"
        return "\n".join(self._format_recap_line(a) for a in acts)

    def _actions_since_previous_turn(
        self, name: str, limit: int
    ) -> list[ActionRecord]:
        """Actions after the previous turn_start; falls back to last N actions."""
        passed_current_start = False
        bucket: list[ActionRecord] = []
        for a in reversed(self.actions):
            if a.agent != name:
                continue
            if a.kind == "turn_start":
                if not passed_current_start:
                    passed_current_start = True
                    continue
                break
            if passed_current_start:
                bucket.append(a)
                if len(bucket) >= limit:
                    break
        if bucket:
            bucket.reverse()
            return bucket
        fallback = [
            a
            for a in reversed(self.actions)
            if a.agent == name and a.kind != "turn_start"
        ][:limit]
        fallback.reverse()
        return fallback

    @staticmethod
    def _format_recap_line(a: ActionRecord) -> str:
        loc = f" @ {a.location}" if a.location else ""
        fail = " [failed]" if not a.ok else ""
        text = (a.detail or a.summary).strip()
        if len(text) > 160:
            text = text[:159] + "…"
        return f"- Tick {a.tick}{loc}: {text}{fail}"

    def agent_stats(self, name: str) -> dict:
        self._ensure_agent(name)
        acts = [a for a in self.actions if a.agent == name]
        return {
            "totalActions": len(acts),
            "toolsUsed": len(self._agent_tools.get(name, set())),
            "locationsVisited": len(self._agent_locations.get(name, set())),
            "lastActionTs": acts[-1].ts if acts else None,
        }

    def ongoing_events(self) -> list[WorldEvent]:
        return [e for e in self.events if e.status == "ongoing"]

    def recent_events(self, limit: int = 25) -> list[WorldEvent]:
        completed = [e for e in self.events if e.status == "completed"]
        ongoing = self.ongoing_events()
        return list(reversed(ongoing + completed[-limit:]))

    def to_action_dict(self, a: ActionRecord) -> dict:
        payload: dict[str, Any] = {
            "id": a.id,
            "tick": a.tick,
            "ts": a.ts,
            "agent": a.agent,
            "kind": a.kind,
            "summary": a.summary,
            "detail": a.detail,
            "tool": a.tool,
            "location": a.location,
            "target": a.target,
            "ok": a.ok,
            "args": _safe_args(a.args) if a.args else {},
        }
        if self.is_thought_record(a, a.agent) or a.kind == "plan":
            full = action_full_text(a)
            if full:
                payload["fullText"] = full
                payload["detail"] = full
        return payload

    def to_event_dict(self, e: WorldEvent) -> dict:
        return {
            "id": e.id,
            "tick": e.tick,
            "ts": e.ts,
            "status": e.status,
            "kind": e.kind,
            "title": e.title,
            "summary": e.summary,
            "agents": e.agents,
            "endedTick": e.ended_tick,
            "endedTs": e.ended_ts,
        }
