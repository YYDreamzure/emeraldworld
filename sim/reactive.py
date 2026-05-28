"""Speech overhearing — delegated to sim.events."""

from __future__ import annotations

from typing import Callable

from sim.events import after_tool
from sim.world import AgentState, WorldState


def trigger_reactions(
    world: WorldState,
    speaker: AgentState,
    message: str,
    *,
    on_update: Callable[[dict], None] | None = None,
) -> None:
    """Legacy entry point; prefer events.after_tool from turn loop."""
    import json

    after_tool(
        world,
        speaker,
        "say_to_agent",
        {"agent": "", "message": message},
        json.dumps({"ok": True}),
        on_update=on_update,
    )
