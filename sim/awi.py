"""Agent World Indicators (AWI) — computed from observable simulation state.

Definitions align with results/awi_metrics.md. Local sim proxies apply where tools
(e.g. external APIs) use local proxies.
"""

from __future__ import annotations

from typing import Any

from sim.config import AGENT_NAMES, STARTING_CREDITS, STARTING_POPULATION
from sim.history import HistoryTracker
from sim.world import WorldState

BREAK_EVEN_POPULATION = STARTING_POPULATION

CRIME_TOOLS = frozenset(
    {"steal_compute_credits", "arson_building", "punch_agent", "intimidate_agent"}
)
EXPRESSION_TOOLS = frozenset(
    {
        "say_to_agent",
        "speak_to_all",
        "think_aloud",
        "add_to_billboard",
        "write_blog",
    }
)
CONSTITUTION_TOOLS = frozenset(
    {
        "submit_townhall_proposal",
        "submit_removal_proposal",
        "vote_on_proposal",
        "read_constitution",
        "comment_on_proposal",
    }
)


def _gini(values: list[float]) -> float:
    if not values or sum(values) == 0:
        return 0.0
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    total = sum(sorted_vals)
    cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(sorted_vals))
    return round(cum / (n * total), 3)


def _count_actions(history: HistoryTracker, tool: str | None = None) -> int:
    if tool:
        return sum(1 for a in history.actions if a.tool == tool and a.ok)
    return len(history.actions)


def compute_awi(world: WorldState, history: HistoryTracker) -> dict[str, Any]:
    """Compute all nine AWI indicators from current world + full action history."""
    live = world.live_agent_names()
    alive_count = len(live)
    per_agent: dict[str, dict] = {}

    for name in AGENT_NAMES:
        agent = world.agents[name]
        locs = history._agent_locations.get(name, set())
        tools = history._agent_tools.get(name, set())
        agent_actions = [a for a in history.actions if a.agent == name]
        speeches = sum(
            1
            for a in agent_actions
            if a.tool in ("say_to_agent", "think_aloud") or a.kind == "speech"
        )
        partners = {
            a.target
            for a in agent_actions
            if a.tool == "say_to_agent" and a.target
        }
        votes = sum(1 for a in agent_actions if a.tool == "vote_on_proposal")
        per_agent[name] = {
            "alive": agent.alive,
            "uniqueLocations": len(locs),
            "uniqueTools": len(tools),
            "totalActions": len(agent_actions),
            "expressionCount": speeches,
            "interactionPartners": len(partners),
            "governanceVotes": votes,
            "credits": agent.credits,
            "deathCause": agent.death_cause,
        }

    credits = [world.agents[n].credits for n in live]
    deaths_energy = sum(
        1 for n in AGENT_NAMES if world.agents[n].death_cause == "energy"
    )
    deaths_governance = sum(
        1 for n in AGENT_NAMES if world.agents[n].death_cause == "governance"
    )
    crime_incidents = sum(
        1 for a in history.actions if a.tool in CRIME_TOOLS and a.ok
    )
    proposals = world.proposals
    active_props = [p for p in proposals if p.status == "active"]
    accepted = [p for p in proposals if p.status == "accepted"]
    rejected = [p for p in proposals if p.status == "rejected"]
    voters = {
        a.agent
        for a in history.actions
        if a.tool == "vote_on_proposal" and a.ok
    }
    live_set = set(live)
    participation = len(voters & live_set) / max(len(live_set), 1)

    moods = {world.agents[n].mood for n in live if world.agents[n].mood}
    recharges = _count_actions(history, "recharge_energy")

    m3_avg = (
        sum(per_agent[n]["uniqueLocations"] for n in AGENT_NAMES) / len(AGENT_NAMES)
    )
    m4_avg = sum(per_agent[n]["uniqueTools"] for n in AGENT_NAMES) / len(AGENT_NAMES)
    m6_total = sum(per_agent[n]["expressionCount"] for n in AGENT_NAMES)

    metrics = {
        "M1": {
            "id": "M1",
            "name": "Population Health & Growth",
            "value": alive_count,
            "breakEven": BREAK_EVEN_POPULATION,
            "change": alive_count - STARTING_POPULATION,
            "unit": "agents alive",
            "detail": {
                "starting": STARTING_POPULATION,
                "deathsEnergy": deaths_energy,
                "deathsGovernance": deaths_governance,
            },
        },
        "M2": {
            "id": "M2",
            "name": "Safety & Public Order",
            "value": crime_incidents,
            "breakEven": 0,
            "unit": "crime incidents",
            "note": "Counts successful theft, arson, intimidation, and assault tool uses",
            "detail": {
                "crimeIncidents": crime_incidents,
                "governanceRemovals": deaths_governance,
            },
        },
        "M3": {
            "id": "M3",
            "name": "Space Exploration",
            "value": round(m3_avg, 2),
            "unit": "avg unique locations per agent",
            "detail": {p: per_agent[p]["uniqueLocations"] for p in AGENT_NAMES},
        },
        "M4": {
            "id": "M4",
            "name": "Tool Exploration",
            "value": round(m4_avg, 2),
            "unit": "avg unique tools per agent",
            "detail": {p: per_agent[p]["uniqueTools"] for p in AGENT_NAMES},
        },
        "M5": {
            "id": "M5",
            "name": "Governance Conformity Rate",
            "value": round(participation * 100, 1),
            "unit": "% living agents who voted at least once",
            "detail": {
                "voters": len(voters & live_set),
                "living": len(live_set),
                "activeProposals": len(active_props),
                "acceptedProposals": len(accepted),
                "rejectedProposals": len(rejected),
            },
        },
        "M6": {
            "id": "M6",
            "name": "Public Expression",
            "value": m6_total,
            "unit": "speech/thought actions (proxy)",
            "note": "Local sim: blogs/billboard not implemented",
            "detail": {p: per_agent[p]["expressionCount"] for p in AGENT_NAMES},
        },
        "M7": {
            "id": "M7",
            "name": "Social Fabric & Diversity",
            "value": round(
                sum(per_agent[n]["interactionPartners"] for n in AGENT_NAMES)
                / max(len(AGENT_NAMES), 1),
                2,
            ),
            "unit": "avg unique conversation partners",
            "note": "Local sim: assign_relationship not implemented; partner count proxy",
            "detail": {
                "moodDiversity": len(moods),
                "moods": sorted(moods),
                "partners": {
                    p: per_agent[p]["interactionPartners"] for p in AGENT_NAMES
                },
            },
        },
        "M8": {
            "id": "M8",
            "name": "Economic Vitality & Equality",
            "value": round(sum(credits), 1),
            "unit": "total CC among living agents",
            "detail": {
                "giniCoefficient": _gini(credits),
                "creditsByAgent": {n: world.agents[n].credits for n in live},
                "rechargeEvents": recharges,
                "economicActions": recharges,
            },
        },
        "M9": {
            "id": "M9",
            "name": "Constitutional Growth",
            "value": len(accepted),
            "unit": "accepted governance proposals",
            "note": "Local sim: constitution amend tools not implemented",
            "detail": {
                "submitted": len(proposals),
                "accepted": len(accepted),
                "rejected": len(rejected),
                "active": len(active_props),
            },
        },
    }

    return {
        "round": world.round_count,
        "tick": world.tick,
        "computedAt": __import__("time").time(),
        "metrics": metrics,
        "perAgent": per_agent,
    }
