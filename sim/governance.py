"""Town Hall proposals, voting, constitution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from sim.config import GOVERNANCE_THRESHOLD, ROOT
from sim.world import WorldState


@dataclass
class Proposal:
    id: str
    kind: str  # removal | general | infrastructure | policy
    proposer: str
    title: str = ""
    description: str = ""
    target_agent: str = ""
    category: str = ""
    tick: int = 0
    votes_for: set[str] = field(default_factory=set)
    votes_against: set[str] = field(default_factory=set)
    status: str = "active"  # active | awaiting_clarification | accepted | rejected
    implementation_status: str = ""  # chosen_to_be_implemented | awaiting_final_report | implemented
    final_report: str = ""
    grant_amount: float = 0.0


def _live_agents(world: WorldState) -> list[str]:
    return [n for n, a in world.agents.items() if a.alive]


def submit_proposal(
    world: WorldState,
    proposer: str,
    *,
    kind: str,
    title: str,
    description: str,
    target_agent: str = "",
    category: str = "general",
    grant_amount: float = 0.0,
) -> tuple[bool, str, Proposal | None]:
    if proposer not in world.agents or not world.agents[proposer].alive:
        return False, "You cannot propose while deceased", None
    if kind == "removal":
        if not target_agent or target_agent not in world.agents:
            return False, "Invalid removal target", None
        if not world.agents[target_agent].alive:
            return False, f"{target_agent} is already removed", None
        if proposer == target_agent:
            return False, "Cannot propose removal of yourself", None

    prop = Proposal(
        id=uuid4().hex[:8],
        kind=kind,
        proposer=proposer,
        title=title or description[:80],
        description=description[:2000],
        target_agent=target_agent,
        category=category,
        tick=world.tick,
        votes_for={proposer},
        grant_amount=grant_amount,
    )
    world.proposals.append(prop)
    world.data.proposal_comments[prop.id] = []
    world.log(f"📜 {proposer} submitted {kind} proposal {prop.id}: {prop.title}")
    _resolve_proposal(world, prop)
    return True, f"Proposal {prop.id} submitted", prop


def submit_removal(world, proposer, target, reason) -> tuple[bool, str, Proposal | None]:
    return submit_proposal(
        world, proposer, kind="removal", title=f"Remove {target}", description=reason, target_agent=target
    )


def vote(world, voter, proposal_id, support) -> tuple[bool, str]:
    if voter not in world.agents or not world.agents[voter].alive:
        return False, "Dead agents cannot vote"
    prop = next((p for p in world.proposals if p.id == proposal_id), None)
    if not prop or prop.status != "active":
        return False, "Proposal not found or already closed"
    if prop.kind == "removal" and voter == prop.target_agent:
        return False, "Target cannot vote on their own removal"

    prop.votes_for.discard(voter)
    prop.votes_against.discard(voter)
    if support:
        prop.votes_for.add(voter)
    else:
        prop.votes_against.add(voter)

    world.log(f"🗳 {voter} voted {'FOR' if support else 'AGAINST'} {prop.id}")
    _resolve_proposal(world, prop)
    return True, f"Vote recorded on {proposal_id}"


def comment_on_proposal(world, agent, proposal_id, comment: str) -> tuple[bool, str]:
    prop = next((p for p in world.proposals if p.id == proposal_id), None)
    if not prop:
        return False, "Proposal not found"
    world.data.proposal_comments.setdefault(proposal_id, []).append(
        {"agent": agent, "comment": comment, "ts": __import__("time").time()}
    )
    return True, "Comment added"


def update_proposal(world, agent, proposal_id, updates: str) -> tuple[bool, str]:
    prop = next((p for p in world.proposals if p.id == proposal_id), None)
    if not prop or prop.proposer != agent:
        return False, "Not found or not your proposal"
    prop.description = (prop.description + "\n" + updates)[:2000]
    if prop.status == "awaiting_clarification":
        prop.status = "active"
    else:
        prop.status = "active"
    return True, "Proposal updated — re-opened for voting"


def _resolve_proposal(world: WorldState, prop: Proposal) -> None:
    live = _live_agents(world)
    if not live:
        return
    needed = max(1, int(len(live) * GOVERNANCE_THRESHOLD + 0.999))
    against = len(prop.votes_against)
    remaining = len(live) - len(prop.votes_for) - len(prop.votes_against)

    if len(prop.votes_for) >= needed:
        prop.status = "accepted"
        prop.implementation_status = "chosen_to_be_implemented"
        if prop.kind == "removal" and prop.target_agent:
            target = world.agents.get(prop.target_agent)
            if target and target.alive:
                world.kill_agent(target, cause="governance", proposal_id=prop.id)
        if prop.category == "constitution" or prop.kind == "infrastructure":
            world.data.constitution_extra.append(f"[{prop.id}] {prop.title}: {prop.description[:200]}")
        if prop.category == "singapore_law":
            from sim.justice import enact_law_amendment_from_proposal

            enact_law_amendment_from_proposal(world, prop)
        if prop.grant_amount > 0:
            impl = world.agents.get(prop.proposer)
            if impl and impl.alive:
                impl.credits += prop.grant_amount
                world.log(f"💰 Research grant {prop.grant_amount:.0f} CC → {prop.proposer}")
        world.log(f"✓ Proposal {prop.id} ACCEPTED")
        return

    if against + remaining < needed:
        prop.status = "rejected"
        world.log(f"✗ Proposal {prop.id} REJECTED")
        return

    if against > len(prop.votes_for) and prop.status == "active":
        prop.status = "awaiting_clarification"


def submit_final_report(
    world: WorldState, agent: str, proposal_id: str, report: str
) -> tuple[bool, str]:
    prop = next((p for p in world.proposals if p.id == proposal_id), None)
    if not prop or prop.status != "accepted":
        return False, "Proposal not found or not accepted"
    if prop.proposer != agent and prop.implementation_status:
        pass
    prop.final_report = report[:4000]
    prop.implementation_status = "implemented"
    world.log(f"📋 Final report for {proposal_id} by {agent}")
    return True, "Final report submitted"


def read_constitution(world: WorldState) -> str:
    base = (ROOT / "data" / "constitution.md").read_text(encoding="utf-8")
    extra = "\n\n".join(world.data.constitution_extra)
    return base + ("\n\n## Amendments\n" + extra if extra else "")


def list_proposals_dict(world: WorldState) -> list[dict]:
    live = len(_live_agents(world))
    needed = max(1, int(live * GOVERNANCE_THRESHOLD + 0.999))
    return [
        {
            "id": p.id,
            "kind": p.kind,
            "proposer": p.proposer,
            "title": p.title,
            "targetAgent": p.target_agent,
            "reason": p.description,
            "status": p.status,
            "votesFor": len(p.votes_for),
            "votesAgainst": len(p.votes_against),
            "votesNeeded": needed,
            "tick": p.tick,
            "comments": len(world.data.proposal_comments.get(p.id, [])),
            "category": p.category,
            "implementationStatus": p.implementation_status,
            "grantAmount": p.grant_amount,
        }
        for p in world.proposals[-30:]
    ]
