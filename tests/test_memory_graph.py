"""Memory graph reinforcement, protection, and decay."""

from sim.memory_graph import (
    AgentMemoryGraph,
    apply_decay,
    ingest,
    refine_soul_belief,
)
from sim.world import AgentState


def test_reinforce_similar_episodic():
    agent = AgentState(name="Test", location_id="central_plaza", home_id="1_maple_row")
    ingest(agent, "Met Flora at the plaza")
    ingest(agent, "Met Flora at the plaza again")
    graph = agent.memory_graph
    assert len(graph.nodes) == 1
    node = next(iter(graph.nodes.values()))
    assert node.reinforcement_count >= 2
    assert node.strength > 40


def test_protected_ltm_no_decay():
    agent = AgentState(name="Test", location_id="central_plaza", home_id="1_maple_row")
    nid = ingest(agent, "Core fact I must keep", protected=True, source="ltm")
    node = agent.memory_graph.nodes[nid]
    before = node.strength
    apply_decay(agent, 3600.0)
    assert agent.memory_graph.nodes[nid].strength == before


def test_episodic_decays():
    agent = AgentState(name="Test", location_id="central_plaza", home_id="1_maple_row")
    ingest(agent, "Forgotten gossip about yesterday")
    node = next(iter(agent.memory_graph.nodes.values()))
    node.last_accessed -= 7200
    apply_decay(agent, 1.0)
    assert node.strength < 35 or node.id not in agent.memory_graph.nodes


def test_refine_soul():
    agent = AgentState(name="Test", location_id="central_plaza", home_id="1_maple_row")
    agent.soul.append("I am not confident")
    ingest(agent, "I am not confident", protected=True, source="soul")
    ok, _ = refine_soul_belief(
        agent,
        0,
        "I am growing confident through practice",
        "I will rehearse conversations daily",
    )
    assert ok
    assert "confident" in agent.soul[0].lower()
