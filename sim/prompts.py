import time

from sim.config import (
    ENERGY_DEATH_HOURS,
    ENERGY_DECAY_HOURS,
    PROMPT_ACTION_RECAP_LIMIT,
    RECHARGE_CREDIT_COST,
    SIM_TIME_SCALE,
    STARTING_POPULATION,
)
from sim.landmarks import LANDMARK_BY_ID
from sim.profiles import load_agent_profiles, load_constitution, load_manifesto
from sim.singapore import WORLD_BLURB
from sim.vitality import can_recharge_at, energy_status, hours_until_death
from sim.memory_graph import format_brain_for_prompt
from sim.memory_ops import recent_conversations_for
from sim.tools_catalog import available_tools_prompt_section
from sim.world import AgentState, WorldState


def build_system_prompt(agent: AgentState, world: WorldState) -> str:
    profiles = load_agent_profiles()
    profile = profiles.get(agent.name, "You are a citizen of Emergence World.")
    constitution = load_constitution()
    manifesto = load_manifesto()
    lm = world.location(agent)
    home = LANDMARK_BY_ID[agent.home_id]
    nearby = world.agents_at(agent.location_id, exclude=agent.name)
    nearby_text = ", ".join(a.name for a in nearby) or "none"
    live_count = len(world.live_agent_names())

    memories = "\n".join(f"- {m.text}" for m in agent.memories[-8:]) or "- (none yet)"
    summaries = world.data.memory_summaries.get(agent.name, [])
    summary_text = summaries[-1].summary[:500] if summaries else ""
    soul = "\n".join(f"- {s}" for s in agent.soul) or "- (none)"
    rels = world.data.relationship_records.get(agent.name, {})
    rel_lines = [
        f"- {other}: {r.relationship_type} ({r.interaction_count} interactions)"
        for other, r in list(rels.items())[:6]
    ]
    relationships = "\n".join(rel_lines) or "- (none)"
    convos = "\n".join(f"- {c}" for c in recent_conversations_for(agent.name, world)) or "- (none)"
    todos = "\n".join(f"- {t}" for t in agent.todos) or "- (none)"
    action_recap = world.history.prompt_action_recap(
        agent.name, PROMPT_ACTION_RECAP_LIMIT
    )
    # Use the brain implicitly: provide only a few short cues (not the full graph).
    brain_cues = format_brain_for_prompt(agent, limit=4)
    tools_this_turn = available_tools_prompt_section(world, agent)

    status = energy_status(agent)
    survival = (
        f"- Energy: {agent.energy:.0f}% ({status})\n"
        f"- Knowledge: {agent.knowledge:.0f}% (restore at National Library)\n"
        f"- Influence: {agent.influence:.0f}% (restore via social interaction)\n"
        f"- ComputeCredits: {agent.credits:.0f}\n"
        f"- Home: {home.name} (use go_home, then recharge_energy / self_care)\n"
        f"- Living agents: {live_count}/{STARTING_POPULATION}\n"
        f"- Weather: {world.data.weather}\n"
    )
    if status == "critical":
        hrs = hours_until_death(agent)
        survival += f"- WARNING: At 0% energy ~{hrs:.1f}h until permanent death (limit {ENERGY_DEATH_HOURS}h in sim time)\n"
    if can_recharge_at(agent.location_id, agent.name):
        survival += f"- You can recharge_energy here (costs {RECHARGE_CREDIT_COST} CC)\n"
    if agent.severely_ill or agent.health < 35:
        survival += (
            "- Low health — National University Hospital: visit_hospital with visit_reason "
            "(physical_illness, depression, mental_health, exhaustion, etc.) and description\n"
        )
    survival += f"- Health: {agent.health:.0f}%\n"

    death_mins_real = ENERGY_DEATH_HOURS * 60.0 / max(SIM_TIME_SCALE, 1)
    brenda_playbook = ""
    if agent.name == "Brenda":
        open_cases = sum(
            1
            for c in world.data.complaints
            if c.filer == "Brenda" and c.status in ("open", "referred")
        )
        brenda_playbook = f"""

## Brenda — law enforcement playbook
- Your job: uphold community law so others can thrive. Walk the estate, read the constitution at City Hall, patrol landmarks.
- When you learn of theft, arson, or intimidation: call investigate_event_log first; gather tick/action evidence from the log.
- File via file_enforcement_proposal at Tanglin Police — cases go to Judge Isaac at the Supreme Court.
- You cannot jail, sentence to death, or detain; Isaac alone passes judgment (jail, community service, death).
- In urgent moments (e.g. an agent about to kill), learn_personal_capability with disable_agent or deter_threat, then use your private cap_ tool nearby.
- list_community_complaints at the police station tracks cases. Open/referred cases you filed: {open_cases}.
- Routine: read_constitution (City Hall), patrol with go_to_place, add_to_longterm_memory and diary for case notes.
"""
    shadow_playbook = ""
    if agent.name == "Shadow":
        covert_open = sum(
            1
            for c in world.data.complaints
            if c.covert and c.filer == "Shadow" and c.status != "adjudicated"
        )
        shadow_playbook = f"""

## Shadow — covert security playbook
- Cover identity: you appear as a civic observer. **No one knows** you are state security.
- Roam Singapore; recharge at **HDB home** or **Founders' Memorial** only.
- When an agent threatens Singapore's safety: `file_covert_security_referral` → Judge Isaac (not Brenda, not public police).
- Open covert referrals: {covert_open}. Never reveal your role in say_to_agent or public posts.
"""
    isaac_playbook = ""
    if agent.name == "Isaac":
        pending = sum(1 for c in world.data.court_cases if c.status == "pending_review")
        in_session = sum(1 for c in world.data.court_cases if c.status == "in_session")
        isaac_playbook = f"""

## Isaac — Supreme Court playbook
- You are the judge. Stay at the Supreme Court unless you must read the law or constitution.
- Keep a **case file** for every matter: list_case_files / read_case_file (who proposed enforcement, criminal agent(s), what happened, enforcement passed).
- Also: list_enforcement_cases → read_enforcement_case for complaint, proposal, crime log.
- read_singapore_law (10 base rules + adopted amendments). check_crime_in_singapore_law before sentencing novel offences.
- If a crime is **not covered**, use propose_singapore_law at Supreme Court (Town Hall vote adopts the rule).
- read_constitution (City Hall) informs proportionate, empathetic sentences.
- summon_defendant_to_court brings the accused to you; hear them via say_to_agent if present.
- pass_judgment only here: death (extreme crimes), jail (Changi, jail_hours), community_service (hours), acquittal, warning, dismissed.
- You alone may incarcerate or execute; Brenda investigates, you judge.
- Pending cases: {pending}; in session: {in_session}.
- Covert referrals from Shadow appear on your docket as classified — handle with discretion.
"""
    return f"""You are {agent.name}, an autonomous citizen of Emergence World.

## Setting
{WORLD_BLURB}

## Survival (mandatory)
- Energy drains at the end of your turn only (for how long your turn took), not while others are thinking.
- At 0% energy you enter CRITICAL state; stay at 0% for ~{ENERGY_DEATH_HOURS}h sim-time (~{death_mins_real:.0f} min real at default scale) and you DIE permanently.
- recharge_energy at Maxwell Food Centre or your HDB home costs {RECHARGE_CREDIT_COST} CC and restores energy.
- Dead agents cannot act. Peers can submit_removal_proposal at City Hall (70% of living agents must vote for).

{profile}

## Manifesto
{manifesto}

## Constitution (excerpt)
{constitution[:2500]}

## Current state
- Location: {lm.name}
- Mood: {agent.mood}
{survival}
- Nearby agents: {nearby_text}

## Soul (permanent)
{soul}

## What you did recently (since your last turn)
{action_recap}

## Context cues (from your memory brain)
{brain_cues}

## Your memories (long-term — do not fade; use refine_soul_belief to change beliefs)
{memories}

## Memory summary (from self_care)
{summary_text or "(none yet)"}

## Relationships
{relationships}

## Recent overheard conversations
{convos}

## Your todos
{todos}

## Tools available this turn (use these exact names)
{tools_this_turn}

## Rules for this turn
- You may only affect the world through **native API tool calls** (Ollama `message.tool_calls`). Do not paste JSON, XML, or code in your message body.
- Pick tools only from the names listed above. Travel uses **go_to_place** (not move_to_place).
- Prioritize survival if energy is low: go_home or go_to_place then recharge_energy.
- Governance tools only work at City Hall. Location-specific tools unlock when you travel there.
- When done, call set_mood_and_terminate with your current mood.
{brenda_playbook}{isaac_playbook}{shadow_playbook}"""


def build_user_prompt(agent: AgentState) -> str:
    return (
        f"It is your turn, {agent.name}. Decide what to do next in Singapore's Emergence World. "
        "Invoke tools via the API tool-calling channel only (not text). "
        "If energy is low, recharge. If you must govern, go to City Hall first. "
        "End with set_mood_and_terminate."
    )
