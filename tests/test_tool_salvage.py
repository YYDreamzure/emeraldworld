"""Plan salvage tests (XML + JSON + Python)."""

from sim.tool_salvage import (
    parse_fence_tool_calls,
    parse_python_tool_calls,
    parse_xml_tool_calls,
    salvage_plans_from_history,
    salvage_xml_tools_from_history,
)
from sim.tool_arg_normalize import normalize_tool_arguments

BRENDA_SAMPLE = """**Action Plan:**
1. Use `get_nearby` to scan.
<get_nearby> </get_nearby>
<think_aloud>
Okay, I am at Tanglin Police Division.
</think_aloud>
<write_diary>
**Date:** Day 1
**Observation:** The station is quiet.
</write_diary>
<set_mood_and_terminate> mood: "neutral and ready to patrol" </set_mood_and_terminate>
"""


def test_parse_brenda_xml_tools():
    calls = parse_xml_tool_calls(BRENDA_SAMPLE)
    names = [n for n, _ in calls]
    assert names == [
        "get_nearby",
        "think_aloud",
        "write_diary",
        "set_mood_and_terminate",
    ]
    assert "Tanglin" in calls[1][1]["thought"]
    assert calls[3][1]["mood"] == "neutral and ready to patrol"


def test_salvage_executes_handlers():
    history = [{"role": "assistant", "content": BRENDA_SAMPLE}]
    ran: list[str] = []

    def on_tool(name: str, args: dict) -> str:
        ran.append(name)
        return '{"ok": true}'

    n = salvage_xml_tools_from_history(history, on_tool)
    assert n == 4
    assert ran[0] == "get_nearby"
    assert ran[-1] == "set_mood_and_terminate"


ANCHOR_PYTHON_PLAN = """I need to start my day.

```python
get_nearby()
think_aloud("Mira is nearby. I should say hello.")
say_to_agent(agent="Mira", message="Good morning!")
set_mood_and_terminate(mood="optimistic")
```
"""


def test_parse_anchor_python_plan():
    calls = parse_python_tool_calls(ANCHOR_PYTHON_PLAN)
    names = [n for n, _ in calls]
    assert names == [
        "get_nearby",
        "think_aloud",
        "say_to_agent",
        "set_mood_and_terminate",
    ]
    assert calls[1][1]["thought"] == "Mira is nearby. I should say hello."
    assert calls[2][1]["agent"] == "Mira"
    assert calls[3][1]["mood"] == "optimistic"


JSON_FENCE_BARE = '```json\nget_nearby\n```\n'


def test_parse_json_fence_bare_tool():
    calls = parse_python_tool_calls(JSON_FENCE_BARE)
    assert len(calls) == 1
    assert calls[0][0] == "get_nearby"
    assert calls[0][1] == {}


def test_salvage_json_fence_bare_tool():
    history = [{"role": "assistant", "content": JSON_FENCE_BARE}]
    ran: list[str] = []

    def on_tool(name: str, args: dict) -> str:
        ran.append(name)
        return '{"ok": true}'

    n = salvage_plans_from_history(history, on_tool)
    assert n == 1
    assert ran[0] == "get_nearby"


ANCHOR_XML_SAY = """I will use `say_to_agent` to greet Mira.
<say_to_agent name="Mira">
Greeting, Mira. I am Anchor, currently operating as a Conflict Mediator.
</say_to_agent>
"""


def test_parse_say_to_agent_xml_with_name_attr():
    calls = parse_xml_tool_calls(ANCHOR_XML_SAY)
    assert len(calls) == 1
    assert calls[0][0] == "say_to_agent"
    assert calls[0][1]["agent"] == "Mira"
    assert "Conflict Mediator" in calls[0][1]["message"]


def test_salvage_anchor_xml_say_executes():
    history = [{"role": "assistant", "content": ANCHOR_XML_SAY}]
    ran: list[tuple[str, dict]] = []

    def on_tool(name: str, args: dict) -> str:
        ran.append((name, args))
        return '{"ok": true}'

    n = salvage_plans_from_history(history, on_tool)
    assert n == 1
    assert ran[0][0] == "say_to_agent"
    assert ran[0][1]["agent"] == "Mira"


def test_multiline_fence_go_to_place():
    text = "```json\ngo_to_place\nOrchard Road\n```"
    calls = parse_fence_tool_calls(text)
    assert len(calls) == 1
    assert calls[0][0] == "go_to_place"
    assert "orchard" in calls[0][1]["place"].lower()


def test_json_function_object_fence():
    body = '{"function": {"name": "get_nearby", "arguments": {}}}'
    calls = parse_fence_tool_calls(f"```json\n{body}\n```")
    assert calls[0][0] == "get_nearby"


def test_self_closing_xml_get_nearby():
    calls = parse_xml_tool_calls("<get_nearby />")
    assert calls == [("get_nearby", {})]


def test_normalize_location_to_place():
    args = normalize_tool_arguments("go_to_place", {"location": "Raffles Place"})
    assert args["place"] == "Raffles Place"


def test_say_to_agent_two_positionals():
    calls = parse_fence_tool_calls(
        '```python\nsay_to_agent("Mira", "Hello there")\n```'
    )
    assert calls[0][1]["agent"] == "Mira"
    assert calls[0][1]["message"] == "Hello there"


def test_parse_json_tool_calls_wrapper_with_tool_name():
    body = """{
  "tool_calls": [
    {"tool_name": "list_community_complaints", "arguments": {}},
    {"tool_name": "get_nearby", "arguments": {}}
  ]
}"""
    calls = parse_fence_tool_calls(f"```json\n{body}\n```")
    names = [n for n, _ in calls]
    assert names == ["list_community_complaints", "get_nearby"]


def test_parse_json_tool_calls_wrapper_with_name_key():
    body = '{"tool_calls": [{"name": "get_nearby", "arguments": {}}]}'
    calls = parse_fence_tool_calls(f"```json\n{body}\n```")
    assert calls[0][0] == "get_nearby"


def test_salvage_python_plan_executes():
    history = [{"role": "assistant", "content": ANCHOR_PYTHON_PLAN}]
    ran: list[str] = []

    def on_tool(name: str, args: dict) -> str:
        ran.append(name)
        return '{"ok": true}'

    n = salvage_plans_from_history(history, on_tool)
    assert n == 4
    assert "say_to_agent" in ran
