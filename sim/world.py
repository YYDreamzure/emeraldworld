from dataclasses import dataclass, field
import math
import time
from typing import Callable

from sim.activity import assign_preferred_period
from sim.config import AGENT_NAMES, AGENT_START_LOCATIONS, HOME_LOCATIONS, STARTING_CREDITS
from sim.history import HistoryTracker, WorldEvent
from uuid import uuid4
from sim.landmarks import LANDMARK_BY_ID, Landmark
from sim.memory_graph import AgentMemoryGraph
from sim.world_data import MemoryEntry, WorldData


EventCallback = Callable[[str, dict], None]


@dataclass
class AgentState:
    name: str
    location_id: str
    home_id: str = ""
    x: float = 0.0
    z: float = 0.0
    mood: str = "neutral"
    energy: float = 80.0
    knowledge: float = 80.0
    influence: float = 80.0
    credits: float = STARTING_CREDITS
    gesture: str | None = None
    alive: bool = True
    energy_zero_since: float | None = None
    last_energy_update: float = field(default_factory=time.time)
    memories: list[MemoryEntry] = field(default_factory=list)
    memory_graph: AgentMemoryGraph = field(default_factory=AgentMemoryGraph)
    soul: list[str] = field(default_factory=list)
    completed_todos: list[str] = field(default_factory=list)
    todos: list[str] = field(default_factory=list)
    terminated: bool = False
    speech: str | None = None
    emoticon: str | None = None
    is_active: bool = False
    death_cause: str | None = None
    jailed_until: float | None = None
    community_service_hours: float = 0.0
    active_court_case_id: str | None = None
    disabled_until: float | None = None
    disabled_by: str | None = None
    activity_window: str = "morning"
    last_location_name: str = ""
    health: float = 100.0
    severely_ill: bool = False


@dataclass
class WorldState:
    agents: dict[str, AgentState]
    public_log: list[str] = field(default_factory=list)
    proposals: list = field(default_factory=list)
    tick: int = 0
    round_count: int = 0
    run_id: str = ""
    started_at: float = 0.0
    ended_at: float | None = None
    active_agent: str | None = None
    running: bool = False
    boost_queue: list[str] = field(default_factory=list)
    sim_started_at: float = 0.0
    history: HistoryTracker = field(default_factory=HistoryTracker)
    data: WorldData = field(default_factory=WorldData)
    store: object | None = field(default=None, repr=False)
    _on_event: EventCallback | None = field(default=None, repr=False)

    def set_event_handler(self, handler: EventCallback | None) -> None:
        self._on_event = handler

    def emit(self, event: str, data: dict | None = None) -> None:
        if self._on_event:
            self._on_event(event, data or {})

    @classmethod
    def bootstrap(cls) -> "WorldState":
        start_locations = [
            "central_plaza",
            "victory_arch",
            "agent_billboard",
            "1_birch_row",
            "1_maple_row",
            "bean_and_brew_charging_station",
            "agent_techhub",
            "riverside_park",
            "central_park",
            "town_center_mall",
        ]
        now = time.time()
        agents = {}
        for i, name in enumerate(AGENT_NAMES):
            home = HOME_LOCATIONS[i % len(HOME_LOCATIONS)]
            loc = AGENT_START_LOCATIONS.get(name, start_locations[i % len(start_locations)])
            agent = AgentState(
                name=name,
                location_id=loc,
                home_id=home,
                last_energy_update=now,
                activity_window=assign_preferred_period(i),
            )
            if name == "Brenda":
                agent.soul = [
                    "I protect order so others can thrive — not through fear, but through fair process.",
                    "I never arrest, fine, or detain on my own authority; enforcement cases go to Judge Isaac.",
                    "Evidence and the constitution come before accusation.",
                ]
            if name == "Isaac":
                agent.soul = [
                    "I judge with Singapore law, reason, and empathy — not popularity.",
                    "Only I may sentence jail at Changi, community service, or death after a fair hearing.",
                    "Brenda brings facts; covert referrals from Shadow also reach my bench.",
                ]
            if name == "Shadow":
                agent.soul = [
                    "No one knows I serve Singapore's security from the shadows.",
                    "I roam, observe, and file covert referrals to Isaac when agents threaten the nation.",
                    "My cover must never slip — I am not Tanglin Police; Brenda is public order, I am state security.",
                ]
            agents[name] = agent
        from sim.store import RunStore, new_run_id

        world = cls(agents=agents)
        now = time.time()
        world.started_at = now
        world.sim_started_at = now
        world.run_id = new_run_id()
        world.data.sim_hour_of_day = 8.0
        world.data.current_activity_window = "morning"
        world.store = RunStore(world.run_id)
        from sim.memory_graph import record_bootstrap_thought, seed_agent_memory_graph

        for agent in world.agents.values():
            world.sync_position(agent)
            seed_agent_memory_graph(agent, world)
            record_bootstrap_thought(world, agent)
        from sim.turn import refresh_weather

        refresh_weather(world)
        world.log(
            "World started — each citizen has a seeded memory graph; "
            "energy decays over time; recharge at HDB or Maxwell; 0% for 48h = death"
        )
        world.store.write_meta(world, status="running")
        world.history.attach(world)
        return world

    def live_agent_names(self) -> list[str]:
        return [n for n in AGENT_NAMES if self.agents[n].alive]

    def sync_position(self, agent: AgentState) -> None:
        lm = LANDMARK_BY_ID[agent.location_id]
        h = hash(agent.name)
        agent.x = lm.x + ((h % 7) - 3) * 4.0
        agent.z = lm.z + (((h >> 4) % 7) - 3) * 4.0

    def location(self, agent: AgentState) -> Landmark:
        return LANDMARK_BY_ID[agent.location_id]

    def agents_at(self, location_id: str, exclude: str | None = None) -> list[AgentState]:
        return [
            a
            for a in self.agents.values()
            if a.alive
            and a.location_id == location_id
            and a.name != exclude
            and not self.data.is_burned(location_id)
        ]

    def is_at_home(self, agent: AgentState) -> bool:
        return agent.location_id.endswith("_row") or agent.location_id == agent.home_id

    def distance(self, a: AgentState, b: AgentState) -> float:
        return math.hypot(a.x - b.x, a.z - b.z)

    def kill_agent(
        self,
        agent: AgentState,
        *,
        cause: str,
        proposal_id: str | None = None,
    ) -> None:
        if not agent.alive:
            return
        agent.alive = False
        agent.is_active = False
        agent.energy = 0.0
        agent.death_cause = cause
        msg = f"💀 {agent.name} has died ({cause})"
        if proposal_id:
            msg += f" [proposal {proposal_id}]"
        self.log(msg)
        self.history.record_action(
            tick=self.tick,
            agent=agent.name,
            kind="death",
            summary=f"Died: {cause}",
        )
        self.history.events.append(
            WorldEvent(
                id=uuid4().hex[:10],
                tick=self.tick,
                ts=time.time(),
                status="completed",
                kind="death",
                title=f"{agent.name} died",
                summary=f"Cause: {cause}",
                agents=[agent.name],
                ended_tick=self.tick,
                ended_ts=time.time(),
            )
        )
        self.emit("death", {"agent": agent.name, "cause": cause})

    def set_speech(self, agent: AgentState, text: str, *, emoticon: str | None = None) -> None:
        agent.speech = text
        agent.emoticon = emoticon
        self.emit("speech", {"agent": agent.name, "text": text, "emoticon": emoticon})

    def clear_speeches(self) -> None:
        for agent in self.agents.values():
            agent.speech = None
            agent.emoticon = None

    def log(self, message: str) -> None:
        self.public_log.append(message)
        if len(self.public_log) > 200:
            self.public_log = self.public_log[-200:]
        self.emit("log", {"message": message})

    def set_active(self, name: str | None) -> None:
        self.active_agent = name
        for agent in self.agents.values():
            agent.is_active = agent.alive and agent.name == name
