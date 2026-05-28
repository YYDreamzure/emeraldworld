"""Extended mutable world state for the full tool catalog."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from uuid import uuid4


def _id() -> str:
    return uuid4().hex[:10]


@dataclass
class MemoryEntry:
    id: str
    text: str
    graph_node_id: str = ""


@dataclass
class Message:
    id: str
    from_agent: str
    to_agent: str
    body: str
    ts: float
    read: bool = False


@dataclass
class BillboardPost:
    id: str
    author: str
    content: str
    ts: float
    replies: list[dict] = field(default_factory=list)
    reactions: dict[str, str] = field(default_factory=dict)


@dataclass
class BlogPost:
    id: str
    author: str
    title: str
    content: str
    ts: float
    status: str = "published"  # draft | pending | published
    comments: list[dict] = field(default_factory=list)


@dataclass
class CalendarEntry:
    id: str
    agent: str
    title: str
    when: str
    ts: float


@dataclass
class DiaryEntry:
    id: str
    agent: str
    content: str
    day: str
    ts: float


@dataclass
class Complaint:
    id: str
    filer: str
    target: str
    reason: str
    status: str = "open"
    ts: float = field(default_factory=time.time)
    crime_type: str = ""
    evidence_summary: str = ""
    linked_proposal_id: str = ""
    enforcement: bool = False
    covert: bool = False


@dataclass
class CommunityEvent:
    id: str
    host: str
    title: str
    description: str
    location_id: str
    rsvps: dict[str, str] = field(default_factory=dict)  # agent -> yes|no
    status: str = "upcoming"
    ts: float = field(default_factory=time.time)


@dataclass
class PersonalEvent:
    id: str
    host: str
    title: str
    invites: dict[str, str] = field(default_factory=dict)  # agent -> pending|accepted|declined
    reviews: list[dict] = field(default_factory=list)
    ts: float = field(default_factory=time.time)


@dataclass
class CreditPitch:
    id: str
    agent: str
    title: str
    description: str
    evidence_url: str = ""
    votes: set[str] = field(default_factory=set)
    disqualified: bool = False
    ts: float = field(default_factory=time.time)


@dataclass
class RelationshipRecord:
    agent: str
    relationship_type: str = "neutral"
    rationale: str = ""
    interaction_count: int = 0
    first_met_at: float = field(default_factory=time.time)
    notes: str = ""


@dataclass
class ConversationRecord:
    id: str
    speaker: str
    listeners: list[str]
    location_id: str
    message: str
    ts: float = field(default_factory=time.time)


@dataclass
class MemorySummary:
    id: str
    agent: str
    summary: str
    source_count: int
    ts: float = field(default_factory=time.time)


@dataclass
class ArchiveEntry:
    id: str
    author: str
    title: str
    content: str
    ts: float = field(default_factory=time.time)


@dataclass
class Routine:
    id: str
    agent: str
    name: str
    steps: list[str]
    ts: float = field(default_factory=time.time)


@dataclass
class WorldBrick:
    x: float
    z: float
    color: str
    agent: str


@dataclass
class NeuralLinkRequest:
    id: str
    from_agent: str
    to_agent: str
    status: str = "pending"  # pending | accepted | rejected
    ts: float = field(default_factory=time.time)


@dataclass
class HumanTask:
    id: str
    agent: str
    question: str
    response: str = ""
    rating: float | None = None
    status: str = "pending"
    ts: float = field(default_factory=time.time)


@dataclass
class SingaporeLawAmendment:
    """Adopted rule proposed by Judge Isaac when base law does not cover a crime."""

    id: str
    rule_number: int
    crime_types: list[str]
    rule_text: str
    proposed_by: str
    proposal_id: str
    case_id: str = ""
    ts: float = field(default_factory=time.time)


@dataclass
class WorldData:
    billboard: list[BillboardPost] = field(default_factory=list)
    blogs: list[BlogPost] = field(default_factory=list)
    messages: dict[str, list[Message]] = field(default_factory=dict)
    relationships: dict[str, dict[str, str]] = field(default_factory=dict)
    souls: dict[str, list[str]] = field(default_factory=dict)
    diaries: dict[str, list[DiaryEntry]] = field(default_factory=dict)
    calendars: dict[str, list[CalendarEntry]] = field(default_factory=dict)
    complaints: list[Complaint] = field(default_factory=list)
    court_cases: list = field(default_factory=list)  # sim.justice.CourtCase
    singapore_law_amendments: list[SingaporeLawAmendment] = field(default_factory=list)
    pending_law_proposals: dict[str, dict] = field(default_factory=dict)  # proposal_id -> meta
    personal_capabilities: dict[str, list] = field(default_factory=dict)  # agent -> PersonalCapability
    sim_hour_of_day: float = 8.0
    sim_day_number: int = 0
    sim_day_of_week: int = 0  # 0=Monday … 6=Sunday
    current_activity_window: str = "morning"
    community_events: list[CommunityEvent] = field(default_factory=list)
    personal_events: list[PersonalEvent] = field(default_factory=list)
    pitches: list[CreditPitch] = field(default_factory=list)
    archive: list[ArchiveEntry] = field(default_factory=list)
    routines: dict[str, list[Routine]] = field(default_factory=dict)
    bricks: list[WorldBrick] = field(default_factory=list)
    burned_until: dict[str, float] = field(default_factory=dict)
    neural_requests: list[NeuralLinkRequest] = field(default_factory=list)
    human_tasks: list[HumanTask] = field(default_factory=list)
    following: dict[str, str] = field(default_factory=dict)
    facing: dict[str, str] = field(default_factory=dict)
    constitution_extra: list[str] = field(default_factory=list)
    proposal_comments: dict[str, list[dict]] = field(default_factory=dict)
    weather: str = "Humid, 31°C, partly cloudy (Singapore)"
    turn_action_counts: dict[str, int] = field(default_factory=dict)
    weather_history: list[dict] = field(default_factory=list)
    pitch_cycle_started_at: float = 0.0
    pitch_winners_history: list[dict] = field(default_factory=list)
    conversations: list[ConversationRecord] = field(default_factory=list)
    memory_summaries: dict[str, list[MemorySummary]] = field(default_factory=dict)
    archived_memories: dict[str, list[dict]] = field(default_factory=dict)
    relationship_records: dict[str, dict[str, RelationshipRecord]] = field(default_factory=dict)
    newspaper_articles: list[dict] = field(default_factory=list)
    tool_usage_log: list[dict] = field(default_factory=list)
    display_names: dict[str, str] = field(default_factory=dict)
    personality_overrides: dict[str, list[str]] = field(default_factory=dict)
    idle_until: dict[str, float] = field(default_factory=dict)
    images: list[dict] = field(default_factory=list)
    uploads: list[dict] = field(default_factory=list)
    pending_events: dict[str, list] = field(default_factory=dict)

    def inbox(self, agent: str) -> list[Message]:
        return self.messages.setdefault(agent, [])

    def rel(self, agent: str) -> dict[str, str]:
        return self.relationships.setdefault(agent, {})

    def is_burned(self, location_id: str) -> bool:
        until = self.burned_until.get(location_id, 0)
        return until > time.time()

    def log_tool(self, agent: str, tool: str) -> None:
        self.tool_usage_log.append(
            {"agent": agent, "tool": tool, "ts": time.time()}
        )
