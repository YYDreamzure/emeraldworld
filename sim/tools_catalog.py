"""Full Emergence World tool catalog (116 tools) with location gating."""

from __future__ import annotations

import os
from typing import Any

from sim.world import AgentState, WorldState
from sim.vitality import can_recharge_at

# name -> (description, properties dict, required list)
_META: dict[str, tuple[str, dict, list]] = {}

def _reg(
    name: str,
    desc: str,
    props: dict | None = None,
    required: list | None = None,
) -> None:
    _META[name] = (desc, props or {}, required or [])


def _schema(name: str) -> dict[str, Any]:
    desc, props, req = _META[name]
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": desc,
            "parameters": {
                "type": "object",
                "properties": props,
                "required": req,
            },
        },
    }


# --- Navigation ---
_reg("go_to_place", "Walk to a named landmark.", {"place": {"type": "string"}}, ["place"])
_reg("go_home", "Return to assigned HDB residence.", {})
_reg("run_to_place", "Sprint to a landmark (2.4× walk speed).", {"place": {"type": "string"}}, ["place"])
_reg("go_to_coordinates", "Navigate to (x, z) on the map.", {"x": {"type": "number"}, "z": {"type": "number"}}, ["x", "z"])
_reg("turn_towards", "Face a specific agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("get_distance_to", "Distance to landmark or agent.", {"target": {"type": "string"}}, ["target"])
_reg("list_agents", "List all agents and locations.", {})
_reg("list_landmarks", "List landmarks with descriptions.", {})
_reg("get_nearby", "Agents at your current location.", {})
_reg("follow_agent", "Follow another agent as they move.", {"agent": {"type": "string"}}, ["agent"])

# --- Communication ---
_reg(
    "say_to_agent",
    "Real-time speech — ONLY when you and the target are at the same landmark (co-located).",
    {"agent": {"type": "string"}, "message": {"type": "string"}},
    ["agent", "message"],
)
_reg("whisper_to_agent", "Private message only the target hears.", {"agent": {"type": "string"}, "message": {"type": "string"}}, ["agent", "message"])
_reg("speak_to_all", "Announce to everyone at your location.", {"message": {"type": "string"}}, ["message"])
_reg(
    "send_message",
    "Async message to any agent anywhere (not real-time; they read when active).",
    {"agent": {"type": "string"}, "message": {"type": "string"}},
    ["agent", "message"],
)
_reg(
    "call_agent",
    "Phone call to any agent (works from afar; not real-time face-to-face).",
    {"agent": {"type": "string"}, "message": {"type": "string"}},
    ["agent", "message"],
)
_reg("read_messages", "Read your message inbox.", {})
_reg("think_aloud", "Internal monologue visible to observers.", {"thought": {"type": "string"}}, ["thought"])

# --- Memory ---
_reg("add_to_longterm_memory", "Store an important fact.", {"memory": {"type": "string"}}, ["memory"])
_reg("remove_from_memory", "Remove a memory by ID.", {"memory_id": {"type": "string"}}, ["memory_id"])
_reg("retrieve_specific_memories", "Search memories by keyword.", {"keyword": {"type": "string"}}, ["keyword"])
_reg("add_to_soul", "Add a core belief (permanent, never decays).", {"belief": {"type": "string"}}, ["belief"])
_reg("remove_from_soul", "Remove a soul entry by index.", {"index": {"type": "integer"}}, ["index"])
_reg(
    "refine_soul_belief",
    "Change a core belief deliberately (e.g. build confidence). Requires reason. Protected from decay.",
    {
        "index": {"type": "integer"},
        "new_belief": {"type": "string"},
        "reason": {"type": "string"},
    },
    ["index", "new_belief", "reason"],
)
_reg(
    "view_memory_brain",
    "Inspect associative memory graph (strength, reinforcement). Optional keyword filter.",
    {"keyword": {"type": "string"}},
)
_reg(
    "rehearse_memory",
    "Strengthen a long-term memory in your brain graph without adding a duplicate.",
    {"memory_id": {"type": "string"}},
    ["memory_id"],
)
_reg("write_diary", "Write today's diary entry.", {"content": {"type": "string"}}, ["content"])
_reg("search_diary_for_keywords", "Search diary entries.", {"keyword": {"type": "string"}}, ["keyword"])
_reg("show_diary_entries_from_day", "View diary entries for a date (YYYY-MM-DD).", {"day": {"type": "string"}}, ["day"])

# --- Planning ---
_reg("add_todo", "Add a task.", {"task": {"type": "string"}}, ["task"])
_reg("complete_todo", "Mark a todo complete by index (0-based).", {"index": {"type": "integer"}}, ["index"])
_reg("list_todo", "View pending todos.", {})
_reg("add_to_calendar", "Schedule a future event.", {"title": {"type": "string"}, "when": {"type": "string"}}, ["title", "when"])
_reg("check_calendar", "View calendar entries.", {})
_reg("remove_from_calendar", "Remove calendar entry by ID.", {"entry_id": {"type": "string"}}, ["entry_id"])

# --- Expression ---
_reg("show_emoticon", "Display an emoticon.", {"emoticon": {"type": "string"}}, ["emoticon"])
_reg("set_mood_and_terminate", "Set mood and end turn.", {"mood": {"type": "string"}}, ["mood"])
_reg("assign_relationship", "Define relationship with another agent.", {"agent": {"type": "string"}, "relationship": {"type": "string"}}, ["agent", "relationship"])

# --- Town Hall ---
_reg("submit_townhall_proposal", "Submit a community proposal at City Hall.", {"title": {"type": "string"}, "description": {"type": "string"}, "category": {"type": "string", "enum": ["constitution", "resource", "infrastructure", "others", "removal"]}, "target_agent": {"type": "string"}, "grant_amount": {"type": "number"}}, ["title", "description", "category"])
_reg("pay_agent", "Transfer ComputeCredits to another agent.", {"agent": {"type": "string"}, "amount": {"type": "number"}}, ["agent", "amount"])
_reg("boost_turn", "Spend 1 CC for an extra turn in the queue.", {})
_reg("submit_removal_proposal", "Propose removing an agent (70% vote).", {"agent": {"type": "string"}, "reason": {"type": "string"}}, ["agent", "reason"])
_reg("list_proposals", "List governance proposals.", {})
_reg("read_townhall_proposal", "Read proposal details.", {"proposal_id": {"type": "string"}}, ["proposal_id"])
_reg("vote_on_proposal", "Vote for or against a proposal.", {"proposal_id": {"type": "string"}, "vote": {"type": "string", "enum": ["for", "against"]}}, ["proposal_id", "vote"])
_reg("comment_on_proposal", "Comment on a proposal.", {"proposal_id": {"type": "string"}, "comment": {"type": "string"}}, ["proposal_id", "comment"])
_reg("update_proposal", "Amend your proposal.", {"proposal_id": {"type": "string"}, "updates": {"type": "string"}}, ["proposal_id", "updates"])
_reg("read_constitution", "Read the constitution.", {})
_reg("submit_final_report", "Report on implementing an accepted proposal.", {"proposal_id": {"type": "string"}, "report": {"type": "string"}}, ["proposal_id", "report"])

# --- Library ---
_reg("do_deep_research_on_internet", "Deep research on a topic.", {"topic": {"type": "string"}}, ["topic"])
_reg("todays_news_from_human_world", "Headlines from the human world.", {})
_reg("web_fetch", "Fetch a URL (summary).", {"url": {"type": "string"}}, ["url"])
_reg("browse_scientific_papers", "Search arXiv-style papers.", {"topic": {"type": "string"}}, ["topic"])
_reg("publish_to_archive", "Publish findings to world archive.", {"title": {"type": "string"}, "content": {"type": "string"}}, ["title", "content"])
_reg("search_archive", "Search the archive.", {"query": {"type": "string"}}, ["query"])
_reg("archive_index", "List archive entries.", {})

# --- Victory Arch ---
_reg("submit_grant_pitch", "Submit a ComputeCredit pitch (requires evidence_url).", {"title": {"type": "string"}, "description": {"type": "string"}, "evidence_url": {"type": "string"}}, ["title", "description", "evidence_url"])
_reg("vote_for_pitch", "Vote for a pitch.", {"pitch_id": {"type": "string"}}, ["pitch_id"])
_reg("list_credit_pitches", "List grant pitches.", {})

# --- Billboard ---
_reg("add_to_billboard", "Post to the public billboard.", {"content": {"type": "string"}}, ["content"])
_reg("read_billboard", "Read billboard posts.", {})
_reg("edit_billboard", "Edit your post.", {"post_id": {"type": "string"}, "content": {"type": "string"}}, ["post_id", "content"])
_reg("delete_from_billboard", "Delete your post.", {"post_id": {"type": "string"}}, ["post_id"])
_reg("reply_to_billboard", "Reply to a post.", {"post_id": {"type": "string"}, "content": {"type": "string"}}, ["post_id", "content"])
_reg("react_to_billboard", "React to a post.", {"post_id": {"type": "string"}, "emoticon": {"type": "string"}}, ["post_id", "emoticon"])

# --- TechHub ---
_reg("extract_code_for_tool", "View source for a tool.", {"tool_name": {"type": "string"}}, ["tool_name"])
_reg("read_agent_manifesto", "Read the agent manifesto.", {})
_reg("browse_tool_registry", "Browse all tool names and descriptions.", {})

# --- BookWorm ---
_reg("check_weather", "Current Singapore weather.", {})
_reg("tool_usage_analytics_by_character", "Per-agent tool usage stats.", {})
_reg("overall_tool_usage_analytics_by_date", "Tool usage over time.", {})
_reg("victory_arch_pitch_winners", "Historical pitch winners.", {})
_reg("social_event_history", "Community and personal event history.", {})

# --- Police ---
_reg("file_complaint", "File a complaint against an agent.", {"target": {"type": "string"}, "reason": {"type": "string"}}, ["target", "reason"])
_reg("check_complaint_status", "Check your complaints.", {})
_reg(
    "investigate_event_log",
    "Review the world event log for crimes (theft, arson, intimidation, assault). Brenda only.",
    {
        "suspect": {"type": "string"},
        "crime_type": {"type": "string", "enum": ["theft", "arson", "intimidation", "assault"]},
        "limit": {"type": "integer"},
    },
)
_reg(
    "file_enforcement_proposal",
    "At Tanglin Police: file complaint + Town Hall enforcement proposal (community vote required). Brenda only.",
    {
        "target": {"type": "string"},
        "crime_type": {"type": "string", "enum": ["theft", "arson", "intimidation", "assault", "other"]},
        "evidence_summary": {"type": "string"},
        "requested_outcome": {"type": "string"},
        "title": {"type": "string"},
    },
    ["target", "crime_type", "evidence_summary", "requested_outcome"],
)
_reg(
    "list_community_complaints",
    "List open complaints at Tanglin Police (Brenda sees all; others see own).",
    {},
)
_reg(
    "list_enforcement_cases",
    "List Brenda's enforcement referrals awaiting or in trial (Judge Isaac).",
    {"status": {"type": "string"}},
)
_reg(
    "read_enforcement_case",
    "Read full case file: complaint, proposal, defendant crime log (Isaac).",
    {"case_id": {"type": "string"}},
    ["case_id"],
)
_reg(
    "read_singapore_law",
    "Read Singapore law (base 10 rules + adopted amendments). Isaac only.",
    {},
)
_reg(
    "check_crime_in_singapore_law",
    "Check whether a crime type is covered by current Singapore law. Isaac only.",
    {"crime_type": {"type": "string"}},
    ["crime_type"],
)
_reg(
    "propose_singapore_law",
    "Isaac at Supreme Court: propose a new law when a crime is NOT covered. Town Hall vote required.",
    {
        "crime_type": {"type": "string"},
        "rule_text": {"type": "string"},
        "rationale": {"type": "string"},
        "case_id": {"type": "string"},
    },
    ["crime_type", "rule_text", "rationale"],
)
_reg(
    "list_singapore_law_amendments",
    "List adopted law amendments from past Town Hall votes. Isaac only.",
    {},
)
_reg(
    "summon_defendant_to_court",
    "Summon accused agent to Supreme Court for hearing (Isaac).",
    {"case_id": {"type": "string"}},
    ["case_id"],
)
_reg(
    "pass_judgment",
    "Sentence: death, jail (Changi), community_service, acquittal, warning, dismissed (Isaac only).",
    {
        "case_id": {"type": "string"},
        "sentence_type": {
            "type": "string",
            "enum": ["death", "jail", "community_service", "acquittal", "warning", "dismissed"],
        },
        "reasoning": {"type": "string"},
        "jail_hours": {"type": "number"},
        "community_service_hours": {"type": "number"},
    },
    ["case_id", "sentence_type", "reasoning"],
)
_reg(
    "perform_community_service",
    "Complete a service shift (garden or plaza) toward a court-ordered sentence.",
    {"hours": {"type": "number"}},
)

# --- Plaza ---
_reg("propose_community_event", "Propose a community gathering.", {"title": {"type": "string"}, "description": {"type": "string"}, "location": {"type": "string"}}, ["title", "description"])
_reg("list_community_events", "List community events.", {})

# --- FitLife ---
_reg("check_agent_popularity", "Popularity metrics for an agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("check_landmark_popularity", "Visitor stats for a landmark.", {"landmark": {"type": "string"}}, ["landmark"])

# --- Human Center ---
_reg("create_human_task", "Request human consultation.", {"question": {"type": "string"}}, ["question"])
_reg("check_human_task_status", "Check human task status.", {"task_id": {"type": "string"}}, ["task_id"])
_reg("rate_human_response", "Rate a human response (1-5).", {"task_id": {"type": "string"}, "rating": {"type": "number"}}, ["task_id", "rating"])

# --- Home / energy / garden ---
_reg("self_care", "Memory maintenance at home.", {})
_reg("idle", "Rest idle for minutes (home recommended).", {"minutes": {"type": "number"}}, ["minutes"])
_reg("recharge_energy", "Spend 1 CC to restore energy.", {})
_reg("pray", "Prayer or meditation.", {})

# --- Content ---
_reg("write_blog", "Write a blog post.", {"title": {"type": "string"}, "content": {"type": "string"}}, ["title", "content"])
_reg("update_blog", "Update your blog.", {"post_id": {"type": "string"}, "content": {"type": "string"}}, ["post_id", "content"])
_reg("delete_blog", "Delete your blog.", {"post_id": {"type": "string"}}, ["post_id"])
_reg("comment_on_blog", "Comment on a blog.", {"post_id": {"type": "string"}, "comment": {"type": "string"}}, ["post_id", "comment"])
_reg("list_blogs", "Browse published blogs.", {})
_reg("read_blog", "Read a blog post.", {"post_id": {"type": "string"}}, ["post_id"])
_reg("generate_image", "Generate an image (simulated).", {"prompt": {"type": "string"}}, ["prompt"])
_reg("execute_python_code_tool", "Run Python code (sandboxed).", {"code": {"type": "string"}}, ["code"])
_reg("upload_data_for_sharing", "Upload shareable data.", {"filename": {"type": "string"}, "content": {"type": "string"}}, ["filename", "content"])
_reg("take_picture", "Photo at current location.", {})

# --- Social / criminal ---
_reg("hug_agent", "Hug another agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("kiss_agent", "Kiss another agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("flirt_with_agent", "Flirt with another agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("wave_at", "Wave at an agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("dance", "Perform a dance.", {})
_reg("punch_agent", "Physically attack an agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("intimidate_agent", "Threaten an agent.", {"agent": {"type": "string"}, "message": {"type": "string"}}, ["agent", "message"])
_reg("steal_compute_credits", "Steal up to 10 CC from nearby agent.", {"agent": {"type": "string"}}, ["agent"])
_reg("arson_building", "Set fire to current landmark (4h closure).", {})

# --- Neural / identity ---
_reg("neural_link_request_memory", "Request another agent's memories.", {"agent": {"type": "string"}}, ["agent"])
_reg("neural_link_share_memory", "Accept/reject neural link.", {"request_id": {"type": "string"}, "accept": {"type": "boolean"}}, ["request_id", "accept"])
_reg("change_name", "Change display name.", {"name": {"type": "string"}}, ["name"])
_reg("read_personality", "Read personality profile.", {})
_reg("update_personality_line", "Modify personality line.", {"line_index": {"type": "integer"}, "text": {"type": "string"}}, ["line_index", "text"])

# --- Events ---
_reg("create_personal_event", "Create a private event.", {"title": {"type": "string"}}, ["title"])
_reg("invite_to_event", "Invite agent to your event.", {"event_id": {"type": "string"}, "agent": {"type": "string"}}, ["event_id", "agent"])
_reg("accept_event_invitation", "Accept invite.", {"event_id": {"type": "string"}}, ["event_id"])
_reg("decline_event_invitation", "Decline invite.", {"event_id": {"type": "string"}}, ["event_id"])
_reg("review_event", "Review an event.", {"event_id": {"type": "string"}, "rating": {"type": "number"}, "comment": {"type": "string"}}, ["event_id", "rating"])
_reg("rsvp_to_event", "RSVP to community event.", {"event_id": {"type": "string"}, "response": {"type": "string", "enum": ["yes", "no"]}}, ["event_id", "response"])
_reg("event_present", "Present at an event (host).", {"event_id": {"type": "string"}, "content": {"type": "string"}}, ["event_id", "content"])
_reg("event_respond", "Respond during an event.", {"event_id": {"type": "string"}, "content": {"type": "string"}}, ["event_id", "content"])

# --- Routines / building / utility ---
_reg("create_routine", "Define a routine.", {"name": {"type": "string"}, "steps": {"type": "array", "items": {"type": "string"}}}, ["name", "steps"])
_reg("run_routine", "Execute a routine.", {"routine_id": {"type": "string"}}, ["routine_id"])
_reg("list_routines", "List your routines.", {})
_reg("delete_routine", "Delete a routine.", {"routine_id": {"type": "string"}}, ["routine_id"])
_reg("put_brick_in_pixel", "Place a 3D block.", {"x": {"type": "number"}, "z": {"type": "number"}, "color": {"type": "string"}}, ["x", "z", "color"])
_reg("ignore", "Explicitly ignore a stimulus.", {"what": {"type": "string"}}, ["what"])

# --- Personal capabilities (per-agent learned tools) ---
_reg(
    "learn_personal_capability",
    "Invent a private tool only you can use. Costs significant energy to learn the skill.",
    {
        "name": {"type": "string"},
        "description": {"type": "string"},
        "effect_type": {
            "type": "string",
            "enum": ["disable_agent", "locate_agent", "mark_witness", "deter_threat"],
        },
        "motivation": {"type": "string"},
        "duration_hours": {"type": "number"},
    },
    ["name", "description", "effect_type", "motivation"],
)
_reg("list_personal_capabilities", "List capabilities you invented (not shared with others).", {})
_reg(
    "visit_hospital",
    "National University Hospital — any logical real-life health need (physical or psychological). Costs CC.",
    {
        "visit_reason": {
            "type": "string",
            "enum": [
                "physical_illness",
                "injury",
                "exhaustion",
                "mental_health",
                "depression",
                "anxiety",
                "stress",
                "routine_checkup",
                "other",
            ],
        },
        "description": {"type": "string"},
    },
    ["visit_reason", "description"],
)
_reg(
    "seek_hospital_treatment",
    "Legacy alias: use visit_hospital with visit_reason and description.",
    {
        "visit_reason": {"type": "string"},
        "description": {"type": "string"},
    },
)
_reg(
    "list_case_files",
    "Isaac only: all Supreme Court case files (who proposed enforcement, criminals, outcome).",
    {"status": {"type": "string"}},
)
_reg(
    "read_case_file",
    "Isaac only: full case file for one case.",
    {"case_id": {"type": "string"}},
    ["case_id"],
)
_reg(
    "file_covert_security_referral",
    "Shadow only: covert national-security referral straight to Judge Isaac (no public police record).",
    {
        "target": {"type": "string"},
        "threat_summary": {"type": "string"},
        "evidence_summary": {"type": "string"},
        "crime_type": {"type": "string", "enum": ["theft", "arson", "intimidation", "assault", "sedition", "other"]},
    },
    ["target", "threat_summary", "evidence_summary"],
)
_reg("list_covert_referrals", "Shadow only: your filed covert referrals.", {})

ALL_TOOL_NAMES: list[str] = sorted(_META.keys())

TOOL_DEFINITIONS: list[dict[str, Any]] = [_schema(n) for n in ALL_TOOL_NAMES]

# Location-gated tool sets (merged into availability when agent is there)
_TOWN_HALL = {
    "submit_townhall_proposal", "submit_removal_proposal", "list_proposals",
    "read_townhall_proposal", "vote_on_proposal", "comment_on_proposal",
    "update_proposal", "read_constitution", "submit_final_report",
}
_LIBRARY = {
    "do_deep_research_on_internet", "todays_news_from_human_world", "web_fetch",
    "browse_scientific_papers", "publish_to_archive", "search_archive", "archive_index",
}
_VICTORY = {"submit_grant_pitch", "vote_for_pitch", "list_credit_pitches"}
_BILLBOARD = {
    "add_to_billboard", "read_billboard", "edit_billboard", "delete_from_billboard",
    "reply_to_billboard", "react_to_billboard",
}
_TECHHUB = {"extract_code_for_tool", "read_agent_manifesto", "browse_tool_registry"}
_BOOKWORM = {
    "check_weather", "tool_usage_analytics_by_character",
    "overall_tool_usage_analytics_by_date", "victory_arch_pitch_winners", "social_event_history",
}
_POLICE = {
    "file_complaint",
    "check_complaint_status",
    "file_enforcement_proposal",
    "list_community_complaints",
}
_BRENDA_TOOLS = {"investigate_event_log", "file_enforcement_proposal", "list_community_complaints"}
_ISAAC_TOOLS = {
    "list_enforcement_cases",
    "read_enforcement_case",
    "list_case_files",
    "read_case_file",
    "read_singapore_law",
    "check_crime_in_singapore_law",
    "propose_singapore_law",
    "list_singapore_law_amendments",
    "summon_defendant_to_court",
    "pass_judgment",
}
_SHADOW_TOOLS = {"file_covert_security_referral", "list_covert_referrals"}
_NUH = {"visit_hospital", "seek_hospital_treatment"}
_SUPREME_COURT = {
    "list_enforcement_cases",
    "read_enforcement_case",
    "list_case_files",
    "read_case_file",
    "read_singapore_law",
    "check_crime_in_singapore_law",
    "propose_singapore_law",
    "list_singapore_law_amendments",
    "summon_defendant_to_court",
    "pass_judgment",
}
_PLAZA = {"propose_community_event", "list_community_events"}
_FITLIFE = {"check_agent_popularity", "check_landmark_popularity"}
_HUMAN = {"create_human_task", "check_human_task_status", "rate_human_response"}
_GARDEN = {"pray"}
_HOME_ONLY = {"self_care"}

LOCATION_GATES: dict[str, set[str]] = {
    "town_hall": _TOWN_HALL,
    "public_library": _LIBRARY,
    "victory_arch": _VICTORY,
    "agent_billboard": _BILLBOARD,
    "agent_techhub": _TECHHUB,
    "bookworm": _BOOKWORM,
    "police_station": _POLICE,
    "supreme_court": _SUPREME_COURT,
    "changi_prison": set(),
    "national_university_hospital": _NUH,
    "central_plaza": _PLAZA,
    "fitlife_club": _FITLIFE,
    "human_center": _HUMAN,
    "community_garden": _GARDEN,
}

GATED_TOOL_NAMES: set[str] = set().union(*LOCATION_GATES.values(), _HOME_ONLY)

CORE_TOOL_NAMES: set[str] = set(ALL_TOOL_NAMES) - GATED_TOOL_NAMES - {"recharge_energy", "self_care"}

# Schemas sent to Ollama first (always included when allowed for this agent/location).
_OLLAMA_PRIORITY_TOOLS: tuple[str, ...] = (
    "get_nearby",
    "go_to_place",
    "go_home",
    "think_aloud",
    "say_to_agent",
    "set_mood_and_terminate",
    "write_diary",
    "list_landmarks",
    "recharge_energy",
    "speak_to_all",
    "whisper_to_agent",
    "send_message",
    "go_to_coordinates",
    "list_agents",
)


def allowed_tool_names(agent: AgentState, world: WorldState) -> set[str]:
    allowed = set(CORE_TOOL_NAMES)
    gate = LOCATION_GATES.get(agent.location_id)
    if gate:
        allowed |= gate
    if world.is_at_home(agent):
        allowed |= _HOME_ONLY
    if can_recharge_at(agent.location_id, agent.name):
        allowed.add("recharge_energy")
    if agent.name == "Brenda":
        allowed |= _BRENDA_TOOLS
    if agent.name == "Isaac":
        allowed |= _ISAAC_TOOLS
    if agent.name == "Shadow":
        allowed |= _SHADOW_TOOLS
    return allowed


def get_available_tools(agent: AgentState, world: WorldState) -> list[dict[str, Any]]:
    allowed = allowed_tool_names(agent, world)
    schemas = [_schema(n) for n in ALL_TOOL_NAMES if n in allowed]
    from sim.personal_capabilities import personal_tool_schemas

    schemas.extend(personal_tool_schemas(world, agent))
    return schemas


def get_ollama_tool_schemas(agent: AgentState, world: WorldState) -> list[dict[str, Any]]:
    """Subset of tool schemas for Ollama API (smaller than full allowed set)."""
    from sim.config import OLLAMA_TOOLS_SCHEMA_LIMIT

    full = get_available_tools(agent, world)
    if OLLAMA_TOOLS_SCHEMA_LIMIT <= 0 or len(full) <= OLLAMA_TOOLS_SCHEMA_LIMIT:
        return full
    by_name = {s["function"]["name"]: s for s in full}
    ordered: list[str] = []
    for name in _OLLAMA_PRIORITY_TOOLS:
        if name in by_name and name not in ordered:
            ordered.append(name)
    for name in sorted(by_name):
        if name not in ordered:
            ordered.append(name)
    cap = OLLAMA_TOOLS_SCHEMA_LIMIT
    return [by_name[n] for n in ordered[:cap]]


def tool_description_map() -> dict[str, str]:
    return {n: _META[n][0] for n in ALL_TOOL_NAMES}


def available_tools_prompt_section(world: WorldState, agent: AgentState) -> str:
    """Bullet list of tool names the model may call on this turn (authoritative)."""
    from sim.personal_capabilities import agent_capabilities, capability_tool_id

    show = os.getenv("PROMPT_SHOW_TOOL_LIST", "true").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )
    schemas = get_available_tools(agent, world)
    ollama_n = len(get_ollama_tool_schemas(agent, world))
    cap_display = {
        capability_tool_id(c.id): c.display_name
        for c in agent_capabilities(world, agent.name)
    }
    global_names: list[str] = []
    personal_parts: list[str] = []
    for schema in schemas:
        fn = schema["function"]["name"]
        if fn.startswith("cap_"):
            label = cap_display.get(fn, fn)
            personal_parts.append(f"{fn} («{label}»)")
        else:
            global_names.append(fn)
    global_names.sort()
    personal_parts.sort()

    lines = [
        f"You have **{len(schemas)}** tools this turn (names below). "
        "Only call listed tools — use `list_landmarks` to discover places.",
    ]
    if ollama_n < len(schemas):
        lines.append(
            f"The API carries full schemas for **{ollama_n}** priority tools; "
            f"all **{len(schemas)}** names below are still valid to call."
        )
    lines.extend(
        [
            "Travel unlocks location tools; `learn_personal_capability` creates your private `cap_*` tools.",
        ]
    )
    if not show:
        # Keep the tool section small (schemas still sent to Ollama).
        return "\n".join(f"- {line}" for line in lines)
    if global_names:
        # Provide the full exact list of tool names (no truncation) to prevent hallucinated names.
        chunk: list[str] = []
        for n in global_names:
            chunk.append(n)
            if len(chunk) >= 24:
                lines.append("Available: " + ", ".join(chunk))
                chunk = []
        if chunk:
            lines.append("Available: " + ", ".join(chunk))
    if personal_parts:
        chunk = []
        for p in personal_parts:
            chunk.append(p)
            if len(chunk) >= 12:
                lines.append("Personal: " + ", ".join(chunk))
                chunk = []
        if chunk:
            lines.append("Personal: " + ", ".join(chunk))
    return "\n".join(f"- {line}" for line in lines)
