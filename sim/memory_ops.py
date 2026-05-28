"""Conversation history, relationships, self-care summarization."""

from __future__ import annotations

import time
from uuid import uuid4

from sim.config import (
    MAX_CONVERSATION_HISTORY,
    SELF_CARE_BATCH_SIZE,
    SELF_CARE_MIN_MEMORIES,
)
from sim.ollama import chat
from sim.world import AgentState, WorldState
from sim.world_data import ConversationRecord, MemorySummary, RelationshipRecord, _id


def record_conversation(
    world: WorldState,
    speaker: str,
    message: str,
    *,
    location_id: str,
    listeners: list[str],
) -> None:
    world.data.conversations.append(
        ConversationRecord(
            id=_id(),
            speaker=speaker,
            listeners=listeners,
            location_id=location_id,
            message=message[:2000],
        )
    )
    if len(world.data.conversations) > MAX_CONVERSATION_HISTORY:
        world.data.conversations = world.data.conversations[-MAX_CONVERSATION_HISTORY:]


def recent_conversations_for(agent: str, world: WorldState, limit: int = 8) -> list[str]:
    lines: list[str] = []
    for c in reversed(world.data.conversations):
        if c.speaker == agent or agent in c.listeners:
            lines.append(f"{c.speaker} @ {c.location_id}: {c.message[:120]}")
        if len(lines) >= limit:
            break
    return lines


def touch_relationship(world: WorldState, agent: str, other: str, relationship: str | None = None) -> None:
    recs = world.data.relationship_records.setdefault(agent, {})
    if other not in recs:
        recs[other] = RelationshipRecord(agent=other, first_met_at=time.time())
    rec = recs[other]
    rec.interaction_count += 1
    if relationship:
        rec.relationship_type = relationship


def run_self_care(world: WorldState, agent: AgentState) -> dict:
    """Summarize memories per docs/MEMORY.md (batch + archive)."""
    if len(agent.memories) < SELF_CARE_MIN_MEMORIES:
        trimmed = max(0, len(agent.memories) - 12)
        if trimmed:
            agent.memories = agent.memories[-12:]
        return {"summarized": 0, "note": f"Need {SELF_CARE_MIN_MEMORIES} memories to summarize"}

    batch = agent.memories[:SELF_CARE_BATCH_SIZE]
    texts = [m.text for m in batch]
    prompt = (
        "Summarize these agent memories into one coherent paragraph of themes and facts:\n"
        + "\n".join(f"- {t}" for t in texts[:80])
    )
    try:
        result = chat([{"role": "user", "content": prompt}], tools=None)
        summary_text = (result.get("message", {}).get("content") or "").strip()[:4000]
    except Exception:
        summary_text = "Summary: " + "; ".join(texts[:5])[:2000]

    archived = world.data.archived_memories.setdefault(agent.name, [])
    archived.extend({"id": m.id, "text": m.text} for m in batch)
    agent.memories = agent.memories[len(batch) :]

    summary = MemorySummary(
        id=_id(), agent=agent.name, summary=summary_text, source_count=len(batch)
    )
    world.data.memory_summaries.setdefault(agent.name, []).append(summary)
    return {"summarized": len(batch), "summaryId": summary.id}
