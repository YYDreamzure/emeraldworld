#!/usr/bin/env python3
"""Smoke-test native Ollama tool_calls for the configured model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sim.config import OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_TOOL_CHOICE  # noqa: E402

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_nearby",
            "description": "Agents at your current location.",
            "parameters": {"type": "object", "properties": {}},
        },
    }
]


def main() -> int:
    payload = {
        "model": OLLAMA_MODEL,
        "stream": False,
        "think": False,
        "messages": [
            {
                "role": "user",
                "content": "Call get_nearby only. Use the tool API; no prose.",
            }
        ],
        "tools": TOOLS,
        "tool_choice": OLLAMA_TOOL_CHOICE if OLLAMA_TOOL_CHOICE not in ("", "none") else "required",
    }
    print(f"POST {OLLAMA_HOST}/api/chat model={OLLAMA_MODEL} tool_choice={payload['tool_choice']}")
    with httpx.Client(timeout=120.0) as client:
        r = client.post(f"{OLLAMA_HOST}/api/chat", json=payload)
    if r.status_code != 200:
        print(f"FAIL HTTP {r.status_code}: {r.text[:500]}")
        return 1
    message = r.json().get("message", {})
    calls = message.get("tool_calls") or []
    content = (message.get("content") or "").strip()
    print(f"tool_calls: {len(calls)}")
    if calls:
        print(json.dumps(calls[0], indent=2)[:400])
    print(f"content length: {len(content)}")
    if not calls:
        print("FAIL: empty message.tool_calls — model or tool_choice not working.")
        return 1
    name = (calls[0].get("function") or {}).get("name", "")
    if name != "get_nearby":
        print(f"WARN: expected get_nearby, got {name!r}")
    print("OK: native tool_calls channel works.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
