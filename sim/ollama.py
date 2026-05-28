import time
import json
from typing import Any, Callable

import httpx

from sim.config import (
    MAX_LLM_ROUNDS_PER_TURN,
    OLLAMA_HOST,
    OLLAMA_MODEL,
    OLLAMA_REQUEST_TIMEOUT_SECONDS,
    OLLAMA_TOOL_CHOICE,
)


class OllamaError(RuntimeError):
    pass


def _parse_tool_call(call: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """Normalize Ollama/OpenAI-style and common alternate tool_call shapes."""
    fn = call.get("function")
    if isinstance(fn, dict):
        name = str(fn.get("name", "")).strip()
        args = fn.get("arguments") or {}
    else:
        name = str(
            call.get("name") or call.get("tool_name") or call.get("tool") or ""
        ).strip()
        args = call.get("arguments") or call.get("args") or {}
    if isinstance(args, str):
        args = json.loads(args) if args else {}
    if not isinstance(args, dict):
        args = {}
    from sim.tool_arg_normalize import normalize_tool_name

    return normalize_tool_name(name), args


def _apply_tool_choice(payload: dict[str, Any], tool_choice: str | None) -> None:
    raw = tool_choice if tool_choice is not None else OLLAMA_TOOL_CHOICE
    choice = raw.strip().lower()
    if choice in ("", "none", "off", "false"):
        return
    if choice in ("auto", "required", "any"):
        payload["tool_choice"] = choice
    else:
        payload["tool_choice"] = raw.strip()


def chat(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    model: str = OLLAMA_MODEL,
    *,
    tool_choice: str | None = None,
    timeout_seconds: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
    }
    if tools:
        payload["tools"] = tools
        _apply_tool_choice(payload, tool_choice)

    timeout = float(timeout_seconds if timeout_seconds is not None else OLLAMA_REQUEST_TIMEOUT_SECONDS)
    with httpx.Client(timeout=timeout) as client:
        response = client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
        if response.status_code != 200:
            raise OllamaError(
                f"Ollama chat failed ({response.status_code}): {response.text}"
            )
        return response.json()


def run_tool_loop(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    on_tool_call,
    max_rounds: int = MAX_LLM_ROUNDS_PER_TURN,
    *,
    tool_choice: str | None = None,
    max_wall_seconds: float | None = None,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    history = list(messages)
    started = time.time()
    for _ in range(max_rounds):
        if should_stop and should_stop():
            return history
        if max_wall_seconds is not None and (time.time() - started) >= max_wall_seconds:
            return history
        remaining = None
        if max_wall_seconds is not None:
            remaining = max(1.0, max_wall_seconds - (time.time() - started))
        result = chat(
            history,
            tools=tools,
            tool_choice=tool_choice,
            timeout_seconds=remaining,
        )
        message = result.get("message", {})
        history.append(message)

        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            return history

        for call in tool_calls:
            if should_stop and should_stop():
                return history
            name, args = _parse_tool_call(call)
            if not name:
                continue
            output = on_tool_call(name, args)
            history.append(
                {
                    "role": "tool",
                    "tool_name": name,
                    "content": output,
                }
            )
    return history
