#!/usr/bin/env python3
import argparse
import sys

import httpx

from sim.config import AGENT_NAMES, OLLAMA_HOST, OLLAMA_MODEL
from sim.turn import run_agent_turn
from sim.world import WorldState


def check_ollama() -> None:
    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.get(f"{OLLAMA_HOST}/api/tags")
            response.raise_for_status()
            models = {m["name"] for m in response.json().get("models", [])}
    except httpx.HTTPError as exc:
        print(f"Cannot reach Ollama at {OLLAMA_HOST}: {exc}", file=sys.stderr)
        sys.exit(1)

    if OLLAMA_MODEL not in models and f"{OLLAMA_MODEL}:latest" not in models:
        print(
            f"Model '{OLLAMA_MODEL}' not found. Run: ollama pull {OLLAMA_MODEL}",
            file=sys.stderr,
        )
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Emergence World locally with Ollama"
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Number of full round-robin cycles (default: 1)",
    )
    parser.add_argument(
        "--agent",
        type=str,
        default=None,
        help="Run a single agent turn instead of full round-robin",
    )
    args = parser.parse_args()

    check_ollama()
    world = WorldState.bootstrap()
    print(f"Emergence World local sim — Ollama {OLLAMA_MODEL} @ {OLLAMA_HOST}\n")

    if args.agent:
        name = args.agent
        if name not in world.agents:
            print(f"Unknown agent '{name}'. Choose from: {', '.join(AGENT_NAMES)}")
            sys.exit(1)
        run_agent_turn(world, world.agents[name])
        return

    for _ in range(args.rounds):
        for name in AGENT_NAMES:
            run_agent_turn(world, world.agents[name])


if __name__ == "__main__":
    main()
