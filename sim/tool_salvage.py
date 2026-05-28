"""Execute plan text (XML / JSON / Python fences) as real tool invocations."""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Callable
from functools import lru_cache
from typing import Any

from sim.tool_arg_normalize import normalize_tool_arguments, normalize_tool_name

# Opening tag: <say_to_agent name="Mira">...</say_to_agent>
_XML_TAG_RE = re.compile(
    r"<([a-z][a-z0-9_]*)\s*([^>/]*?)>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)
_XML_SELF_RE = re.compile(
    r"<([a-z][a-z0-9_]*)\s*([^>/]*?)\s*/\s*>",
    re.IGNORECASE,
)

_XML_ATTR_RE = re.compile(
    r'(\w+)\s*=\s*(["\'])(.*?)\2',
    re.IGNORECASE | re.DOTALL,
)

_XML_TOOL_HINT = re.compile(
    r"<\s*([a-z][a-z0-9_]{2,})\b",
    re.IGNORECASE,
)

_FENCE_RE = re.compile(
    r"```[a-z]*\s*\n?(.*?)```",
    re.IGNORECASE | re.DOTALL,
)

_INLINE_CALL_LINE = re.compile(
    r"^\s*([a-z][a-z0-9_]*)\s*\(",
    re.IGNORECASE,
)

_TOOL_NAME_LINE = re.compile(r"^([a-z][a-z0-9_]*)$", re.IGNORECASE)

_PYTHON_TOOL_HINT = re.compile(
    r"\b([a-z][a-z0-9_]{3,})\s*\(",
    re.IGNORECASE,
)

# Tools where the next non-tool line is the single string argument.
_SINGLE_LINE_ARG: dict[str, str] = {
    "go_to_place": "place",
    "run_to_place": "place",
    "think_aloud": "thought",
    "write_diary": "content",
    "add_to_longterm_memory": "memory",
    "add_to_soul": "belief",
    "speak_to_all": "message",
    "set_mood_and_terminate": "mood",
    "add_todo": "task",
    "add_to_billboard": "content",
}

_POS_ARG_KEY: dict[str, str] = {
    "think_aloud": "thought",
    "write_diary": "content",
    "write_blog": "content",
    "add_to_longterm_memory": "memory",
    "go_to_place": "place",
    "run_to_place": "place",
    "set_mood_and_terminate": "mood",
    "add_to_soul": "belief",
    "speak_to_all": "message",
}


@lru_cache(maxsize=1)
def _no_arg_tool_names() -> frozenset[str]:
    from sim.tools_catalog import _META

    return frozenset(n for n, (_, __, req) in _META.items() if not req)


@lru_cache(maxsize=1)
def _known_tool_names() -> frozenset[str]:
    from sim.tools_catalog import ALL_TOOL_NAMES

    return frozenset(ALL_TOOL_NAMES)


def _is_known_tool(name: str) -> bool:
    n = normalize_tool_name(name.lower().strip())
    if n in _known_tool_names():
        return True
    from sim.personal_capabilities import is_personal_tool

    return is_personal_tool(n)


def history_has_xml_style_tools(history: list[dict]) -> bool:
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        text = msg.get("content") or ""
        if _XML_TOOL_HINT.search(text):
            return True
    return False


def history_has_fence_plan(history: list[dict]) -> bool:
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        text = msg.get("content") or ""
        if _FENCE_RE.search(text) or _PYTHON_TOOL_HINT.search(text):
            return True
    return False


def history_has_python_style_plan(history: list[dict]) -> bool:
    return history_has_fence_plan(history)


def history_has_salvageable_plan(history: list[dict]) -> bool:
    return history_has_xml_style_tools(history) or history_has_fence_plan(history)


def _parse_xml_attrs(attr_str: str) -> dict[str, str]:
    return {k.lower(): v.strip() for k, _, v in _XML_ATTR_RE.findall(attr_str or "")}


def _attr_agent(attrs: dict[str, str]) -> str:
    for key in ("agent", "name", "target", "to"):
        if attrs.get(key):
            return attrs[key]
    return ""


def _attr_place(attrs: dict[str, str], body: str) -> str:
    for key in ("place", "location", "landmark", "name"):
        if attrs.get(key):
            return attrs[key]
    return body.split("\n")[0].strip()[:120]


def _normalize_args(
    tool: str, body: str, attrs: dict[str, str] | None = None
) -> dict[str, Any]:
    body = body.strip()
    tool = tool.lower()
    attrs = attrs or {}
    if tool == "think_aloud":
        return {"thought": body}
    if tool == "write_diary":
        return {"content": body}
    if tool == "write_blog":
        title_line, _, rest = body.partition("\n")
        title = title_line.strip().strip("#").strip()[:200]
        title = attrs.get("title") or title or "Diary"
        return {"title": title[:200], "content": rest.strip() or body}
    if tool == "set_mood_and_terminate":
        mood = attrs.get("mood", "").strip()
        if not mood:
            m = re.search(
                r'mood\s*:\s*["\']?(.+?)["\']?\s*$',
                body,
                re.IGNORECASE | re.DOTALL,
            )
            mood = (m.group(1).strip() if m else body.split("\n")[0].strip())[:80]
        return {"mood": mood or "neutral"}
    if tool in ("say_to_agent", "whisper_to_agent", "send_message", "call_agent"):
        agent = _attr_agent(attrs)
        message = body or attrs.get("message", "")
        return {"agent": agent, "message": message}
    if tool == "speak_to_all":
        return {"message": body or attrs.get("message", "")}
    if tool in ("go_to_place", "run_to_place"):
        place = _attr_place(attrs, body)
        return {"place": place or body}
    if tool == "get_nearby":
        return {}
    if tool == "learn_personal_capability":
        return {
            "name": attrs.get("name", ""),
            "description": attrs.get("description", "") or body[:500],
            "effect_type": attrs.get("effect_type", attrs.get("effect", "")),
            "motivation": attrs.get("motivation", "") or body[:500],
            "duration_hours": float(attrs.get("duration_hours") or 2.0),
        }
    if tool in _no_arg_tool_names():
        return {}
    return {}


def _args_executable(name: str, args: dict[str, Any]) -> bool:
    name = normalize_tool_name(name)
    args = normalize_tool_arguments(name, args)
    if name in _no_arg_tool_names():
        return True
    if name == "get_nearby":
        return True
    if name in ("say_to_agent", "whisper_to_agent", "send_message", "call_agent"):
        return bool(str(args.get("agent", "")).strip()) and bool(
            str(args.get("message", "")).strip()
        )
    if name == "speak_to_all":
        return bool(str(args.get("message", "")).strip())
    if name in ("go_to_place", "run_to_place"):
        return bool(str(args.get("place", "")).strip())
    if name == "think_aloud":
        return bool(str(args.get("thought", "")).strip())
    if name == "write_diary":
        return bool(str(args.get("content", "")).strip())
    if name == "set_mood_and_terminate":
        return bool(str(args.get("mood", "")).strip())
    from sim.tools_catalog import _META

    meta = _META.get(name)
    if not meta:
        return bool(args)
    _desc, _props, required = meta
    for key in required:
        if key not in args:
            return False
        if key == "index":
            continue
        if isinstance(args[key], str) and not args[key].strip():
            return False
    return True


def parse_xml_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    if not text:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for name, attr_str, body in _XML_TAG_RE.findall(text):
        tool = normalize_tool_name(name)
        if not _is_known_tool(tool):
            continue
        attrs = _parse_xml_attrs(attr_str)
        args = normalize_tool_arguments(tool, _normalize_args(tool, body, attrs))
        if _args_executable(tool, args):
            out.append((tool, args))
    for name, attr_str in _XML_SELF_RE.findall(text):
        tool = normalize_tool_name(name)
        if not _is_known_tool(tool):
            continue
        attrs = _parse_xml_attrs(attr_str)
        args = normalize_tool_arguments(tool, _normalize_args(tool, "", attrs))
        if _args_executable(tool, args):
            out.append((tool, args))
    return out


def _ast_literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                parts.append(v.value)
            else:
                return None
        return "".join(parts)
    return None


def _call_to_tool(call: ast.Call) -> tuple[str, dict[str, Any]] | None:
    func = call.func
    if not isinstance(func, ast.Name):
        return None
    name = normalize_tool_name(func.id)
    if not _is_known_tool(name):
        return None
    args: dict[str, Any] = {}
    for kw in call.keywords:
        if kw.arg is None:
            continue
        val = _ast_literal(kw.value)
        if val is not None:
            args[kw.arg] = val
    if name in ("say_to_agent", "whisper_to_agent", "send_message", "call_agent"):
        if len(call.args) >= 2:
            a0, a1 = _ast_literal(call.args[0]), _ast_literal(call.args[1])
            if a0 is not None and a1 is not None:
                args.setdefault("agent", str(a0))
                args.setdefault("message", str(a1))
        elif len(call.args) == 1:
            val = _ast_literal(call.args[0])
            if val is not None and "message" not in args:
                args["message"] = str(val)
    elif call.args:
        key = _POS_ARG_KEY.get(name)
        if key:
            val = _ast_literal(call.args[0])
            if val is not None and key not in args:
                args[key] = val
    args = normalize_tool_arguments(name, args)
    if name in _no_arg_tool_names():
        return name, {}
    if name == "get_nearby":
        return name, {}
    if name == "set_mood_and_terminate" and "mood" not in args:
        args["mood"] = "neutral"
    if name in ("say_to_agent", "whisper_to_agent", "send_message", "call_agent"):
        if not args.get("agent"):
            return None
    if not _args_executable(name, args):
        return None
    return name, args


def _json_tool_call_items(data: Any) -> list[Any]:
    """Unwrap common model shapes: [{...}], {"tool_calls": [...]}, single {...}."""
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    if isinstance(data.get("tool_calls"), list):
        return data["tool_calls"]
    return [data]


def _tool_name_from_json_item(item: dict[str, Any]) -> str:
    if "function" in item and isinstance(item["function"], dict):
        fn = item["function"]
        return str(fn.get("name", "")).strip()
    return str(
        item.get("tool")
        or item.get("name")
        or item.get("tool_name")
        or item.get("function_name")
        or ""
    ).strip()


def _args_from_json_item(item: dict[str, Any], tool: str) -> dict[str, Any]:
    if "function" in item and isinstance(item["function"], dict):
        fn = item["function"]
        raw = fn.get("arguments") or {}
        if isinstance(raw, str):
            try:
                raw = json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                raw = {}
        return raw if isinstance(raw, dict) else {}
    raw_args = item.get("arguments") or item.get("args")
    if isinstance(raw_args, dict):
        return raw_args
    skip = frozenset(
        ("tool", "name", "tool_name", "type", "function", "function_name", "id")
    )
    return {k: v for k, v in item.items() if k not in skip}


def _parse_json_tool_objects(body: str) -> list[tuple[str, dict[str, Any]]]:
    body = body.strip()
    if not body:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return out
    items = _json_tool_call_items(data)
    for item in items:
        if isinstance(item, str) and _is_known_tool(item):
            tool = item.lower()
            args = normalize_tool_arguments(tool, {})
            if _args_executable(tool, args):
                out.append((tool, args))
            continue
        if not isinstance(item, dict):
            continue
        tool = normalize_tool_name(_tool_name_from_json_item(item))
        raw_args = _args_from_json_item(item, tool)
        if not tool or not _is_known_tool(tool):
            continue
        args = normalize_tool_arguments(tool, raw_args)
        if _args_executable(tool, args):
            out.append((tool, args))
    return out


def _parse_bare_fence_lines(body: str) -> list[tuple[str, dict[str, Any]]]:
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    if not lines:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    i = 0
    while i < len(lines):
        m = _TOOL_NAME_LINE.match(lines[i])
        if not m:
            i += 1
            continue
        tool = m.group(1).lower()
        if not _is_known_tool(tool):
            i += 1
            continue
        i += 1
        if tool in _no_arg_tool_names():
            args: dict[str, Any] = {}
        elif tool in _SINGLE_LINE_ARG and i < len(lines):
            arg_key = _SINGLE_LINE_ARG[tool]
            if arg_key and not _TOOL_NAME_LINE.match(lines[i]):
                args = {arg_key: lines[i]}
                i += 1
            else:
                args = {}
        else:
            args = {}
        args = normalize_tool_arguments(tool, args)
        if _args_executable(tool, args):
            out.append((tool, args))
    return out


def _extract_calls_from_fence_block(body: str) -> list[tuple[str, dict[str, Any]]]:
    body = body.strip()
    if not body:
        return []
    json_calls = _parse_json_tool_objects(body)
    if json_calls:
        return json_calls
    bare = _parse_bare_fence_lines(body)
    if bare:
        return bare
    return _extract_calls_from_python(body)


def _extract_calls_from_python(code: str) -> list[tuple[str, dict[str, Any]]]:
    code = code.strip()
    if not code:
        return []
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        parsed = _call_to_tool(node)
        if parsed:
            out.append(parsed)
    return out


def _fence_snippets_from_text(text: str) -> list[str]:
    snippets: list[str] = []
    for m in _FENCE_RE.finditer(text):
        block = m.group(1).strip()
        if block:
            snippets.append(block)
    if snippets:
        return snippets
    lines: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if _INLINE_CALL_LINE.match(stripped):
            lines.append(stripped)
    if lines:
        snippets.append("\n".join(lines))
    return snippets


def parse_fence_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    if not text:
        return []
    out: list[tuple[str, dict[str, Any]]] = []
    for snippet in _fence_snippets_from_text(text):
        out.extend(_extract_calls_from_fence_block(snippet))
    return out


def parse_python_tool_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    return parse_fence_tool_calls(text)


def _iter_planned_calls(text: str) -> list[tuple[str, dict[str, Any]]]:
    return parse_xml_tool_calls(text) + parse_fence_tool_calls(text)


def _tool_valid(name: str) -> bool:
    from sim.personal_capabilities import is_personal_tool
    from sim.tools_exec import HANDLERS

    return name in HANDLERS or is_personal_tool(name)


def _execute_planned_calls(
    history: list[dict],
    on_tool_call: Callable[[str, dict[str, Any]], str],
    *,
    max_calls: int,
) -> int:
    seen: set[str] = set()
    executed = 0
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        text = msg.get("content") or ""
        for name, args in _iter_planned_calls(text):
            if executed >= max_calls:
                return executed
            name = normalize_tool_name(name)
            args = normalize_tool_arguments(name, args)
            if not _tool_valid(name) or not _args_executable(name, args):
                continue
            key = name + ":" + json.dumps(args, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            on_tool_call(name, args)
            executed += 1
    return executed


def salvage_xml_tools_from_history(
    history: list[dict],
    on_tool_call: Callable[[str, dict[str, Any]], str],
    *,
    max_calls: int = 15,
) -> int:
    return _execute_planned_calls(history, on_tool_call, max_calls=max_calls)


def salvage_plans_from_history(
    history: list[dict],
    on_tool_call: Callable[[str, dict[str, Any]], str],
    *,
    max_calls: int = 15,
) -> int:
    return _execute_planned_calls(history, on_tool_call, max_calls=max_calls)


def format_ollama_tool_call(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Shape used by Ollama/OpenAI-style APIs for a single tool invocation."""
    return {
        "function": {
            "name": name,
            "arguments": arguments,
        }
    }


def collect_planned_tool_calls(
    history: list[dict], *, max_calls: int = 15
) -> list[dict[str, Any]]:
    """Parse assistant prose/XML/fences into proper tool_call objects (not executed)."""
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    for msg in history:
        if msg.get("role") != "assistant":
            continue
        text = msg.get("content") or ""
        for name, args in _iter_planned_calls(text):
            if len(out) >= max_calls:
                return out
            name = normalize_tool_name(name)
            args = normalize_tool_arguments(name, args)
            if not _tool_valid(name) or not _args_executable(name, args):
                continue
            key = name + ":" + json.dumps(args, sort_keys=True, default=str)
            if key in seen:
                continue
            seen.add(key)
            out.append(format_ollama_tool_call(name, args))
    return out


def execute_planned_tool_calls_from_history(
    history: list[dict],
    on_tool_call: Callable[[str, dict[str, Any]], str],
    *,
    max_calls: int = 15,
    log: Callable[[str], None] | None = None,
) -> int:
    """Convert prose/XML/fenced tool text to tool_call shape and execute handlers."""
    planned = collect_planned_tool_calls(history, max_calls=max_calls)
    if not planned:
        return 0
    if log:
        log(
            f"  ↳ Converting {len(planned)} prose/XML/fence tool(s) to native tool_call format"
        )
    executed = 0
    for call in planned:
        fn = call.get("function", {})
        name = str(fn.get("name", "")).lower()
        args = fn.get("arguments") or {}
        if not isinstance(args, dict):
            args = {}
        if log:
            log(
                f"  ↳ tool_call {{\"name\": \"{name}\", \"arguments\": "
                f"{json.dumps(args, ensure_ascii=False)}}}"
            )
        on_tool_call(name, args)
        executed += 1
    return executed
