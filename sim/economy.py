"""ComputeCredits economy: pitch cycles, transfers, boost queue."""

from __future__ import annotations

import time

from sim.config import PITCH_CYCLE_HOURS, PITCH_REWARDS, SIM_TIME_SCALE
from sim.world import WorldState


def _cycle_seconds() -> float:
    return PITCH_CYCLE_HOURS * 3600.0 / max(SIM_TIME_SCALE, 0.001)


def maybe_end_pitch_cycle(world: WorldState, now: float | None = None) -> bool:
    """Close pitch cycle and award top 3 if interval elapsed."""
    now = now or time.time()
    if not world.data.pitch_cycle_started_at:
        world.data.pitch_cycle_started_at = now
        return False

    if now - world.data.pitch_cycle_started_at < _cycle_seconds():
        return False

    eligible = [p for p in world.data.pitches if not p.disqualified and p.evidence_url.strip()]
    ranked = sorted(eligible, key=lambda p: len(p.votes), reverse=True)[:3]
    rewards = PITCH_REWARDS
    for i, pitch in enumerate(ranked):
        agent = world.agents.get(pitch.agent)
        if agent and agent.alive and i < len(rewards):
            agent.credits += rewards[i]
            world.log(f"🏆 Pitch cycle: {pitch.agent} +{rewards[i]:.0f} CC for '{pitch.title}'")
            world.data.pitch_winners_history.append(
                {
                    "pitchId": pitch.id,
                    "agent": pitch.agent,
                    "title": pitch.title,
                    "votes": len(pitch.votes),
                    "reward": rewards[i],
                    "ts": now,
                }
            )

    world.data.pitches.clear()
    world.data.pitch_cycle_started_at = now
    return True


def transfer_credits(
    world: WorldState, from_agent: str, to_agent: str, amount: float
) -> tuple[bool, str]:
    sender = world.agents.get(from_agent)
    receiver = world.agents.get(to_agent)
    if not sender or not receiver or not sender.alive:
        return False, "Invalid sender"
    if not receiver.alive:
        return False, "Receiver is deceased"
    amount = max(0.0, float(amount))
    if sender.credits < amount:
        return False, f"Insufficient CC (have {sender.credits:.0f})"
    sender.credits -= amount
    receiver.credits += amount
    world.log(f"💸 {from_agent} paid {to_agent} {amount:.0f} CC")
    return True, f"Transferred {amount:.0f} CC to {to_agent}"


def enqueue_boost(world: WorldState, agent_name: str) -> tuple[bool, str]:
    agent = world.agents.get(agent_name)
    if not agent or not agent.alive:
        return False, "Cannot boost"
    if agent.credits < 1:
        return False, "Need 1 CC for boost turn"
    agent.credits -= 1
    world.boost_queue.append(agent_name)
    world.log(f"⚡ {agent_name} purchased boost turn")
    return True, "Boost turn queued"
