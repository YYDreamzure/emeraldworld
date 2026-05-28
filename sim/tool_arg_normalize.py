"""Normalize common model mistakes in tool names and argument keys."""

from __future__ import annotations

from typing import Any

# Wrong tool names the model invents → registered handler name.
_TOOL_NAME_ALIASES: dict[str, str] = {
    "move_to_place": "go_to_place",
    "move_to": "go_to_place",
    "travel_to": "go_to_place",
    "walk_to_place": "go_to_place",
    "go_to_location": "go_to_place",
    "say_to": "say_to_agent",
    "talk_to_agent": "say_to_agent",
    "end_turn": "set_mood_and_terminate",
    "terminate": "set_mood_and_terminate",
    "list_nearby": "get_nearby",
    "nearby_agents": "get_nearby",
}

# Per-tool: wrong_key -> canonical_key (only if canonical not already set)
_TOOL_ALIASES: dict[str, dict[str, str]] = {
    "go_to_place": {
        "location": "place",
        "landmark": "place",
        "destination": "place",
        "target": "place",
    },
    "run_to_place": {
        "location": "place",
        "landmark": "place",
        "destination": "place",
    },
    "write_diary": {
        "diary_entry": "content",
        "entry": "content",
        "text": "content",
        "body": "content",
    },
    "add_to_longterm_memory": {
        "content": "memory",
        "text": "memory",
        "fact": "memory",
    },
    "think_aloud": {"thoughts": "thought", "message": "thought", "text": "thought"},
    "say_to_agent": {
        "to": "agent",
        "target": "agent",
        "name": "agent",
        "recipient": "agent",
        "text": "message",
        "content": "message",
        "body": "message",
    },
    "whisper_to_agent": {
        "to": "agent",
        "target": "agent",
        "name": "agent",
        "text": "message",
        "content": "message",
    },
    "send_message": {
        "to": "agent",
        "target": "agent",
        "name": "agent",
        "text": "message",
        "content": "message",
    },
    "call_agent": {
        "to": "agent",
        "target": "agent",
        "name": "agent",
        "text": "message",
        "content": "message",
    },
    "speak_to_all": {"text": "message", "content": "message", "body": "message"},
    "add_to_soul": {"content": "belief", "text": "belief", "belief_text": "belief"},
    "follow_agent": {"target": "agent", "name": "agent", "to": "agent"},
    "turn_towards": {"target": "agent", "name": "agent", "to": "agent"},
    "set_mood_and_terminate": {"mood_name": "mood", "feeling": "mood"},
    "add_todo": {"todo": "task", "content": "task", "text": "task"},
    "file_complaint": {"agent": "target", "against": "target"},
    "learn_personal_capability": {
        "effect": "effect_type",
        "type": "effect_type",
        "skill": "effect_type",
        "title": "name",
        "capability_name": "name",
        "why": "motivation",
        "reason": "motivation",
        "purpose": "description",
        "summary": "description",
        "duration": "duration_hours",
    },
}


def normalize_tool_name(name: str) -> str:
    key = (name or "").strip().lower()
    return _TOOL_NAME_ALIASES.get(key, key)


def normalize_tool_arguments(tool: str, args: dict[str, Any] | None) -> dict[str, Any]:
    if not args:
        return {}
    tool = tool.lower().strip()
    out = dict(args)
    for old, new in _TOOL_ALIASES.get(tool, {}).items():
        if old in out and (new not in out or not str(out.get(new, "")).strip()):
            val = out.pop(old)
            if val is not None:
                out[new] = val
    return out
