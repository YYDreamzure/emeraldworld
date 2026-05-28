"""Per-agent associative memory graph (brain): reinforce repeats, decay unused episodic links."""

from __future__ import annotations

import math
import re
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING
from uuid import uuid4

from sim.config import (
    MEMORY_GRAPH_MAX_EDGES,
    MEMORY_GRAPH_MAX_NODES,
    MEMORY_GRAPH_MIN_STRENGTH,
    MEMORY_GRAPH_SIMILARITY_THRESHOLD,
    SIM_TIME_SCALE,
)

if TYPE_CHECKING:
    from sim.world import AgentState


def _nid() -> str:
    return uuid4().hex[:10]


_WORD_RE = re.compile(r"[a-z0-9]+", re.I)


def _tokenize(text: str) -> set[str]:
    return {w.lower() for w in _WORD_RE.findall(text) if len(w) > 2}


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 1.0 if a.strip().lower() == b.strip().lower() and a.strip() else 0.0
    inter = len(ta & tb)
    union = len(ta | tb)
    return inter / union if union else 0.0


@dataclass
class BrainNode:
    id: str
    text: str
    strength: float = 40.0
    access_count: int = 0
    reinforcement_count: int = 1
    last_accessed: float = field(default_factory=time.time)
    created_at: float = field(default_factory=time.time)
    protected: bool = False
    source: str = "episodic"  # episodic | ltm | soul
    linked_memory_id: str = ""
    tags: list[str] = field(default_factory=list)
    # Per-agent "round" bookkeeping (a round == one apply_decay call for this agent).
    last_reinforced_round: int = 0


@dataclass
class BrainEdge:
    id: str
    a: str
    b: str
    weight: float = 20.0
    last_accessed: float = field(default_factory=time.time)
    last_reinforced_round: int = 0


@dataclass
class AgentMemoryGraph:
    nodes: dict[str, BrainNode] = field(default_factory=dict)
    edges: list[BrainEdge] = field(default_factory=list)
    round_counter: int = 0


def get_brain(agent: AgentState) -> AgentMemoryGraph:
    g = getattr(agent, "memory_graph", None)
    if g is None or not isinstance(g, AgentMemoryGraph):
        g = AgentMemoryGraph()
        agent.memory_graph = g
    return g


def _find_similar(graph: AgentMemoryGraph, text: str) -> BrainNode | None:
    best: BrainNode | None = None
    best_score = MEMORY_GRAPH_SIMILARITY_THRESHOLD
    for node in graph.nodes.values():
        score = _similarity(node.text, text)
        if score >= best_score and (best is None or score > best_score):
            best = node
            best_score = score
    return best


def _touch(node: BrainNode, *, reinforce: bool = False, round_id: int | None = None) -> None:
    now = time.time()
    node.last_accessed = now
    node.access_count += 1
    if reinforce:
        node.reinforcement_count += 1
        # Policy: repeats strengthen the node by +25% (cap at 100).
        node.strength = min(100.0, node.strength * 1.25)
        if round_id is not None:
            node.last_reinforced_round = round_id
    else:
        # Access does not count as a "repeat" for reinforcement policy.
        node.strength = min(100.0, node.strength + 2.0)


def _edge_key(a: str, b: str) -> tuple[str, str]:
    return (a, b) if a < b else (b, a)


def _link_nodes(
    graph: AgentMemoryGraph, id_a: str, id_b: str, delta: float = 8.0, *, round_id: int | None = None
) -> None:
    if id_a == id_b:
        return
    ka, kb = _edge_key(id_a, id_b)
    for edge in graph.edges:
        if _edge_key(edge.a, edge.b) == (ka, kb):
            # Policy: repeated link strengthens by +25% (cap at 100).
            edge.weight = min(100.0, edge.weight * 1.25)
            edge.last_accessed = time.time()
            if round_id is not None:
                edge.last_reinforced_round = round_id
            return
    graph.edges.append(
        BrainEdge(
            id=_nid(),
            a=ka,
            b=kb,
            weight=20.0 + delta * 0.5,
            last_accessed=time.time(),
            last_reinforced_round=round_id or 0,
        )
    )
    if len(graph.edges) > MEMORY_GRAPH_MAX_EDGES:
        graph.edges.sort(key=lambda e: e.weight)
        graph.edges = graph.edges[-MEMORY_GRAPH_MAX_EDGES:]


def _recent_episodic_ids(graph: AgentMemoryGraph, limit: int = 4) -> list[str]:
    episodic = [n for n in graph.nodes.values() if not n.protected and n.source == "episodic"]
    episodic.sort(key=lambda n: n.last_accessed, reverse=True)
    return [n.id for n in episodic[:limit]]


def ingest(
    agent: AgentState,
    text: str,
    *,
    protected: bool = False,
    source: str = "episodic",
    linked_memory_id: str = "",
    tags: list[str] | None = None,
) -> str:
    """Add or reinforce a concept in the agent's memory graph. Returns node id."""
    text = (text or "").strip()[:2000]
    if not text:
        return ""
    graph = get_brain(agent)
    # A "round" is counted per-agent; advanced when apply_decay runs.
    round_id = getattr(graph, "round_counter", 0)
    similar = _find_similar(graph, text)
    if similar:
        _touch(similar, reinforce=True, round_id=round_id)
        if protected:
            similar.protected = True
            similar.source = source
        if linked_memory_id:
            similar.linked_memory_id = linked_memory_id
        if tags:
            for t in tags:
                if t and t not in similar.tags:
                    similar.tags.append(t)
        for rid in _recent_episodic_ids(graph):
            _link_nodes(
                graph,
                similar.id,
                rid,
                delta=10.0 if similar.reinforcement_count >= 2 else 5.0,
                round_id=round_id,
            )
        _prune_if_needed(graph)
        return similar.id

    node = BrainNode(
        id=_nid(),
        text=text,
        strength=50.0 if protected else 35.0,
        protected=protected,
        source=source,
        linked_memory_id=linked_memory_id,
        tags=list(tags or [])[:8],
    )
    node.last_reinforced_round = round_id
    graph.nodes[node.id] = node
    for rid in _recent_episodic_ids(graph):
        _link_nodes(graph, node.id, rid, round_id=round_id)
    _prune_if_needed(graph)
    return node.id


def reinforce_linked_memory(agent: AgentState, memory_id: str) -> bool:
    graph = get_brain(agent)
    for node in graph.nodes.values():
        if node.linked_memory_id == memory_id or node.id == memory_id:
            _touch(node, reinforce=True, round_id=getattr(graph, "round_counter", 0))
            return True
    return False


def refine_soul_belief(
    agent: AgentState,
    index: int,
    new_belief: str,
    reason: str,
) -> tuple[bool, str]:
    """Explicit soul change — updates belief and linked protected graph node."""
    new_belief = new_belief.strip()[:500]
    reason = reason.strip()[:500]
    if not new_belief or not reason:
        return False, "new_belief and reason required"
    if index < 0 or index >= len(agent.soul):
        return False, "Invalid soul index"
    old = agent.soul[index]
    agent.soul[index] = new_belief
    graph = get_brain(agent)
    matched = None
    for node in graph.nodes.values():
        if node.source == "soul" and _similarity(node.text, old) >= 0.5:
            matched = node
            break
    if matched:
        matched.text = new_belief
        matched.protected = True
        matched.source = "soul"
        _touch(matched, reinforce=True)
    else:
        ingest(
            agent,
            f"{new_belief} (refined: {reason})",
            protected=True,
            source="soul",
        )
    ingest(
        agent,
        f"I chose to change a core belief: was «{old[:120]}» → now «{new_belief[:120]}». Reason: {reason}",
        protected=True,
        source="ltm",
    )
    return True, "Soul belief updated (protected — will not decay)"


def apply_decay(agent: AgentState, wall_dt_seconds: float) -> dict:
    """Per-round update per spec:

    - Never delete nodes.
    - Strengthen a node and its linkages by +25% when repeated.
    - If a node is not repeated this round, decay its linkages by 5%.
    - Only linkages (edges) may disappear.
    """
    graph = get_brain(agent)
    graph.round_counter = int(getattr(graph, "round_counter", 0)) + 1
    round_id = graph.round_counter

    repeated: set[str] = {n.id for n in graph.nodes.values() if n.last_reinforced_round == round_id}

    # Nodes decay 5% per round if not repeated (nodes never disappear).
    for node in graph.nodes.values():
        if node.protected or node.source in ("soul", "ltm"):
            continue
        if node.id not in repeated:
            node.strength = max(0.0, node.strength * 0.95)

    # Remove edges to missing nodes (nodes never deleted, but keep the guard).
    graph.edges = [e for e in graph.edges if e.a in graph.nodes and e.b in graph.nodes]

    # Edges decay 5% when either endpoint node was not repeated this round.
    for edge in graph.edges:
        if graph.nodes[edge.a].protected and graph.nodes[edge.b].protected:
            continue
        if edge.a not in repeated or edge.b not in repeated:
            edge.weight = max(0.0, edge.weight * 0.95)

    # Only linkages can disappear.
    graph.edges = [e for e in graph.edges if e.weight >= MEMORY_GRAPH_MIN_STRENGTH * 0.3]
    _prune_if_needed(graph)
    return {"edges": len(graph.edges)}


def _prune_if_needed(graph: AgentMemoryGraph) -> None:
    # Nodes never disappear per spec; only prune edges.
    if len(graph.edges) > MEMORY_GRAPH_MAX_EDGES:
        graph.edges.sort(key=lambda e: e.weight)
        graph.edges = graph.edges[-MEMORY_GRAPH_MAX_EDGES:]


def _activation_score(node: BrainNode, now: float) -> float:
    idle_h = max(0.0, (now - node.last_accessed) * SIM_TIME_SCALE / 3600.0)
    recency = math.exp(-idle_h / 72.0)
    repeat = 1.0 + 0.15 * max(0, node.reinforcement_count - 1)
    return node.strength * recency * repeat


def top_nodes_for_prompt(agent: AgentState, limit: int = 8) -> list[BrainNode]:
    graph = get_brain(agent)
    now = time.time()
    ranked = sorted(
        graph.nodes.values(),
        key=lambda n: _activation_score(n, now),
        reverse=True,
    )
    return ranked[:limit]


def format_brain_for_prompt(agent: AgentState, limit: int = 8) -> str:
    nodes = top_nodes_for_prompt(agent, limit)
    if not nodes:
        return "- (brain forming — experiences will link here)"
    lines = []
    for n in nodes:
        tag = "🔒" if n.protected else "○"
        rep = f", ×{n.reinforcement_count}" if n.reinforcement_count > 1 else ""
        lines.append(f"- {tag} [{n.strength:.0f}{rep}] {n.text[:200]}")
    return "\n".join(lines)


def brain_snapshot(agent: AgentState) -> dict:
    graph = get_brain(agent)
    return {
        "nodeCount": len(graph.nodes),
        "edgeCount": len(graph.edges),
        "protectedCount": sum(1 for n in graph.nodes.values() if n.protected),
        "top": [
            {
                "id": n.id,
                "strength": round(n.strength, 1),
                "reinforcementCount": n.reinforcement_count,
                "protected": n.protected,
                "text": n.text[:120],
            }
            for n in top_nodes_for_prompt(agent, 6)
        ],
    }


def brain_graph_for_ui(agent: AgentState, *, max_nodes: int = 80) -> dict:
    """Full graph slice for the client memory visualizer."""
    graph = get_brain(agent)
    ranked = sorted(
        graph.nodes.values(),
        key=lambda n: (n.protected, n.strength, n.last_accessed),
        reverse=True,
    )[:max_nodes]
    id_set = {n.id for n in ranked}
    nodes_out = [
        {
            "id": n.id,
            "text": n.text[:220],
            "strength": round(n.strength, 1),
            "reinforcementCount": n.reinforcement_count,
            "protected": n.protected,
            "source": n.source,
            "accessCount": n.access_count,
        }
        for n in ranked
    ]
    edges_out = [
        {
            "id": e.id,
            "a": e.a,
            "b": e.b,
            "weight": round(e.weight, 1),
        }
        for e in graph.edges
        if e.a in id_set and e.b in id_set
    ][:200]
    snap = brain_snapshot(agent)
    snap["nodes"] = nodes_out
    snap["edges"] = edges_out
    return snap


def seed_agent_memory_graph(agent: AgentState, world: WorldState) -> int:
    """Populate an agent's memory graph at simulation start. Returns node count."""
    from sim.landmarks import LANDMARK_BY_ID
    from sim.profiles import load_agent_profiles

    profiles = load_agent_profiles()
    profile = profiles.get(agent.name, "")
    loc = world.location(agent)
    home = LANDMARK_BY_ID.get(agent.home_id)
    created = 0

    if profile:
        ingest(
            agent,
            f"I am {agent.name}. {profile[:500]}",
            protected=True,
            source="ltm",
            tags=[agent.name],
        )
        created += 1

    ingest(
        agent,
        f"I begin at {loc.name} in Emergence World, Singapore.",
        source="episodic",
        tags=[agent.location_id],
    )
    created += 1

    if home:
        ingest(
            agent,
            f"My home is {home.name} — I can recharge and practice self-care there.",
            protected=True,
            source="ltm",
            tags=[agent.home_id],
        )
        created += 1

    for belief in agent.soul:
        if belief.strip():
            ingest(agent, belief.strip(), protected=True, source="soul")
            created += 1

    ingest(
        agent,
        "The world runs continuously; I choose when to work, rest, socialise, or visit NUH.",
        source="episodic",
    )
    created += 1

    ingest(
        agent,
        "My associative memory brain links ideas — repeats strengthen them; unused episodic links fade.",
        protected=True,
        source="ltm",
    )
    created += 1

    return len(get_brain(agent).nodes)


def record_bootstrap_thought(world: WorldState, agent: AgentState) -> None:
    """Seed the action/thought feed so the Agents tab is populated from tick 0."""
    from sim.profiles import load_agent_profiles

    profiles = load_agent_profiles()
    profile = profiles.get(agent.name, "")[:4000]
    loc_name = world.location(agent).name
    thought = (
        f"I wake at {loc_name} with my memories and purpose intact. "
        f"{profile or 'Today I will explore, connect, and survive in Singapore.'}"
    )
    world.history.record_action(
        tick=0,
        agent=agent.name,
        kind="thought",
        summary="Simulation start — inner monologue",
        detail=thought,
        tool="think_aloud",
        location=loc_name,
    )


def search_brain(agent: AgentState, keyword: str, limit: int = 12) -> list[dict]:
    kw = keyword.lower()
    graph = get_brain(agent)
    hits = []
    for n in graph.nodes.values():
        if kw in n.text.lower():
            _touch(n)
            hits.append(
                {
                    "id": n.id,
                    "text": n.text,
                    "strength": round(n.strength, 1),
                    "reinforcementCount": n.reinforcement_count,
                    "protected": n.protected,
                }
            )
    hits.sort(key=lambda h: h["strength"], reverse=True)
    return hits[:limit]
