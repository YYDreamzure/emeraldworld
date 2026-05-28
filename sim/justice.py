"""Supreme Court cases, sentencing, Changi Prison, and Isaac's case files."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sim.config import ROOT, SIM_TIME_SCALE

if TYPE_CHECKING:
    from sim.world import AgentState, WorldState


CHANGI_PRISON_ID = "changi_prison"
SUPREME_COURT_ID = "supreme_court"

JAILED_ALLOWED_TOOLS = frozenset(
    {
        "idle",
        "set_mood_and_terminate",
        "say_to_agent",
        "think_aloud",
        "show_emoticon",
    }
)


def _id() -> str:
    return uuid4().hex[:10]


def sim_hours_to_seconds(hours: float) -> float:
    return max(0.0, hours) * 3600.0 / max(SIM_TIME_SCALE, 1.0)


def load_singapore_law() -> str:
    path = ROOT / "data" / "singapore_law.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


# Base rules 5–7 map known crime_type values to the 10-rule statute.
_BASE_CRIME_COVERAGE: dict[str, tuple[int, str]] = {
    "theft": (5, "Theft (rule 5)"),
    "steal": (5, "Theft (rule 5)"),
    "arson": (7, "Arson (rule 7)"),
    "violence": (6, "Violence (rule 6)"),
    "assault": (6, "Violence (rule 6)"),
    "intimidation": (6, "Violence (rule 6)"),
    "intimidate": (6, "Violence (rule 6)"),
    "punch": (6, "Violence (rule 6)"),
}


def _normalize_crime(crime_type: str) -> str:
    return crime_type.strip().lower().replace(" ", "_")


def _crime_matches_amendment(crime: str, amendment) -> bool:
    for tag in amendment.crime_types:
        t = _normalize_crime(tag)
        if t == crime or t in crime or crime in t:
            return True
    return False


def crime_covered_by_law(world: WorldState, crime_type: str) -> tuple[bool, str]:
    """Return (covered, explanation) for base law + adopted amendments."""
    crime = _normalize_crime(crime_type)
    if not crime:
        return False, "No crime type specified"

    for amendment in world.data.singapore_law_amendments:
        if _crime_matches_amendment(crime, amendment):
            return True, f"Covered by adopted rule {amendment.rule_number}"

    for key, (_, label) in _BASE_CRIME_COVERAGE.items():
        if key == crime or key in crime:
            return True, label

    if crime in ("other", "unknown", "sedition", "fraud", "vandalism", "trespass"):
        return False, f"Crime '{crime_type}' is not covered by rules 1–9 — Isaac may propose a new law"

    return False, (
        f"Crime '{crime_type}' has no matching rule in the base statute — "
        "use propose_singapore_law at Supreme Court, then Town Hall vote"
    )


def load_singapore_law_text(world: WorldState) -> str:
    base = load_singapore_law()
    if not world.data.singapore_law_amendments:
        return base
    lines = ["\n\n## Adopted amendments (Town Hall)\n"]
    for a in world.data.singapore_law_amendments:
        tags = ", ".join(a.crime_types)
        lines.append(f"{a.rule_number}. **{tags}** — {a.rule_text}")
    return base + "\n".join(lines)


def list_law_amendments_dict(world: WorldState) -> list[dict[str, Any]]:
    return [
        {
            "id": a.id,
            "ruleNumber": a.rule_number,
            "crimeTypes": a.crime_types,
            "ruleText": a.rule_text,
            "proposalId": a.proposal_id,
            "caseId": a.case_id or None,
            "proposedBy": a.proposed_by,
        }
        for a in world.data.singapore_law_amendments
    ]


def enact_law_amendment_from_proposal(world: WorldState, proposal) -> None:
    meta = world.data.pending_law_proposals.pop(proposal.id, None)
    if not meta:
        world.log(f"⚠ Law proposal {proposal.id} accepted but metadata missing — not enacted")
        return
    from sim.world_data import SingaporeLawAmendment

    rule_num = 10 + len(world.data.singapore_law_amendments) + 1
    crime_types = meta.get("crime_types") or [meta.get("crime_type", "other")]
    if isinstance(crime_types, str):
        crime_types = [crime_types]
    amendment = SingaporeLawAmendment(
        id=_id(),
        rule_number=rule_num,
        crime_types=[_normalize_crime(c) for c in crime_types if c],
        rule_text=str(meta.get("rule_text", ""))[:2000],
        proposed_by=meta.get("proposer", proposal.proposer),
        proposal_id=proposal.id,
        case_id=str(meta.get("case_id", "")),
    )
    world.data.singapore_law_amendments.append(amendment)
    world.log(
        f"📜 Singapore law rule {rule_num} adopted ({', '.join(amendment.crime_types)}): "
        f"{amendment.rule_text[:100]}"
    )
    if amendment.case_id:
        case = find_case(world, amendment.case_id)
        if case:
            case.case_file_notes.append(
                f"New law rule {rule_num} adopted via proposal {proposal.id}."
            )


def propose_singapore_law(
    world: WorldState,
    judge: AgentState,
    *,
    crime_type: str,
    rule_text: str,
    rationale: str,
    case_id: str = "",
) -> tuple[bool, str, str | None]:
    """Isaac proposes a new rule; requires Town Hall vote to enact."""
    from sim.governance import submit_proposal

    crime = _normalize_crime(crime_type)
    covered, explain = crime_covered_by_law(world, crime)
    if covered:
        return False, f"Crime already covered: {explain}", None

    rule_text = rule_text.strip()
    rationale = rationale.strip()
    if not rule_text or len(rule_text) < 20:
        return False, "rule_text required (at least 20 characters — the new statutory rule)", None
    if not rationale or len(rationale) < 20:
        return False, "rationale required — why this crime needs a new rule", None

    case = find_case(world, case_id) if case_id else None
    title = f"Adopt Singapore law for: {crime_type}"
    description = (
        f"Judge Isaac proposes a new rule because '{crime_type}' is not covered by the current statute.\n\n"
        f"**Proposed rule:**\n{rule_text}\n\n"
        f"**Rationale:**\n{rationale}\n\n"
        f"**Gap:** {explain}\n"
    )
    if case:
        description += f"\n**Linked case:** {case.id} vs {case.defendant}\n"
    description += "\nIf accepted by Town Hall vote, this rule becomes binding for future sentencing."

    ok_flag, msg, prop = submit_proposal(
        world,
        judge.name,
        kind="policy",
        title=title[:200],
        description=description[:2000],
        category="singapore_law",
    )
    if not prop:
        return ok_flag, msg, None

    world.data.pending_law_proposals[prop.id] = {
        "crime_type": crime,
        "crime_types": [crime],
        "rule_text": rule_text,
        "rationale": rationale,
        "case_id": case_id,
        "proposer": judge.name,
    }
    if case:
        case.case_file_notes.append(
            f"Isaac proposed new law for '{crime_type}' → Town Hall proposal {prop.id}."
        )
    world.log(f"📜 Isaac proposed new Singapore law ({crime_type}) → proposal {prop.id}")
    return True, f"Law proposal {prop.id} submitted — agents must vote at Town Hall", prop.id


@dataclass
class CourtCase:
    id: str
    complaint_id: str
    proposal_id: str
    defendant: str
    prosecutor: str
    crime_type: str
    evidence_summary: str
    status: str = "pending_review"
    judge: str = ""
    verdict: str = ""
    sentence_type: str = ""
    reasoning: str = ""
    jail_hours: float = 0.0
    community_service_hours: float = 0.0
    covert: bool = False
    referred_by: str = ""
    ts: float = field(default_factory=time.time)
    # Case file (Isaac keeps full record per user request)
    proposed_by: str = ""
    defendants: list[str] = field(default_factory=list)
    what_happened: str = ""
    enforcement_passed: str = ""
    case_file_notes: list[str] = field(default_factory=list)


def _build_what_happened(complaint) -> str:
    parts = []
    if complaint.crime_type:
        parts.append(f"Alleged offence: {complaint.crime_type}")
    if complaint.reason:
        parts.append(complaint.reason.strip())
    if complaint.evidence_summary:
        parts.append(f"Evidence on file:\n{complaint.evidence_summary.strip()}")
    return "\n\n".join(parts)[:4000]


def _format_enforcement_passed(case: CourtCase) -> str:
    st = case.sentence_type or case.verdict
    if not st:
        return ""
    lines = [f"Enforcement passed: {st}"]
    if case.reasoning:
        lines.append(f"Judge reasoning: {case.reasoning[:1500]}")
    if st == "jail" and case.jail_hours:
        lines.append(f"Jail: {case.jail_hours:.0f} sim-hours at Changi Prison")
    if st == "community_service" and case.community_service_hours:
        lines.append(f"Community service: {case.community_service_hours:.0f} sim-hours")
    if st == "death":
        lines.append("Sentence: death (agent terminated)")
    return "\n".join(lines)


def case_file_dict(case: CourtCase) -> dict[str, Any]:
    criminals = list(case.defendants) if case.defendants else ([case.defendant] if case.defendant else [])
    return {
        "caseId": case.id,
        "status": case.status,
        "proposedBy": case.proposed_by or case.referred_by or case.prosecutor,
        "prosecutor": case.prosecutor,
        "criminalAgents": criminals,
        "defendant": case.defendant,
        "crimeType": case.crime_type,
        "whatHappened": case.what_happened,
        "evidenceSummary": case.evidence_summary,
        "enforcementPassed": case.enforcement_passed or None,
        "covert": case.covert,
        "judge": case.judge or None,
        "verdict": case.verdict or None,
        "sentenceType": case.sentence_type or None,
        "complaintId": case.complaint_id,
        "proposalId": case.proposal_id,
        "notes": list(case.case_file_notes[-20:]),
        "openedAt": case.ts,
    }


def list_case_files_for_judge(world: WorldState) -> list[dict[str, Any]]:
    return [case_file_dict(c) for c in list_cases_for_judge(world)]


def is_jailed(agent: AgentState) -> bool:
    return agent.jailed_until is not None and time.time() < agent.jailed_until


def community_service_remaining(agent: AgentState) -> float:
    return max(0.0, agent.community_service_hours)


def enforce_custody(world: WorldState, agent: AgentState) -> None:
    now = time.time()
    if agent.jailed_until is not None and now >= agent.jailed_until:
        agent.jailed_until = None
        if agent.location_id == CHANGI_PRISON_ID and agent.alive:
            world.log(f"🔓 {agent.name} completed jail sentence and may leave Changi")
    if is_jailed(agent) and agent.location_id != CHANGI_PRISON_ID:
        agent.location_id = CHANGI_PRISON_ID
        world.sync_position(agent)


def tool_blocked_for_agent(world: WorldState, agent: AgentState, tool: str) -> str | None:
    enforce_custody(world, agent)
    if is_jailed(agent) and tool not in JAILED_ALLOWED_TOOLS:
        remaining_h = (agent.jailed_until - time.time()) / 3600.0 * SIM_TIME_SCALE
        return (
            f"Incarcerated at Changi Prison (~{remaining_h:.1f} sim-hours remaining). "
            f"Allowed: {', '.join(sorted(JAILED_ALLOWED_TOOLS))}"
        )
    if community_service_remaining(agent) > 0 and tool in (
        "steal_compute_credits",
        "arson_building",
        "punch_agent",
        "intimidate_agent",
    ):
        return (
            f"Community service obligation: {agent.community_service_hours:.1f} sim-hours "
            "remaining — complete perform_community_service before criminal acts"
        )
    return None


def movement_blocked(agent: AgentState, destination_id: str) -> str | None:
    if is_jailed(agent) and destination_id != CHANGI_PRISON_ID:
        return "You are serving a jail sentence at Changi Prison and cannot leave"
    return None


def open_case_from_complaint(
    world: WorldState,
    complaint,
    *,
    covert: bool = False,
    referred_by: str = "",
) -> CourtCase:
    proposed = referred_by or complaint.filer
    accused = [complaint.target] if complaint.target else []
    case = CourtCase(
        id=_id(),
        complaint_id=complaint.id,
        proposal_id=complaint.linked_proposal_id,
        defendant=complaint.target,
        prosecutor=complaint.filer,
        crime_type=complaint.crime_type,
        evidence_summary=complaint.evidence_summary,
        covert=covert,
        referred_by=referred_by or complaint.filer,
        proposed_by=proposed,
        defendants=accused,
        what_happened=_build_what_happened(complaint),
    )
    channel = "covert security referral" if covert else "public enforcement proposal"
    case.case_file_notes.append(
        f"Case opened from {channel} by {proposed} against {', '.join(accused) or 'unknown'}."
    )
    world.data.court_cases.append(case)
    complaint.status = "in_court"
    world.log(f"📁 Case file {case.id} opened — proposed by {proposed}")
    return case


def find_case(world: WorldState, case_id: str) -> CourtCase | None:
    return next((c for c in world.data.court_cases if c.id == case_id), None)


def list_cases_for_judge(world: WorldState, *, status: str | None = None) -> list[CourtCase]:
    rows = world.data.court_cases
    if status:
        rows = [c for c in rows if c.status == status]
    return list(reversed(rows[-40:]))


def summon_defendant(world: WorldState, case: CourtCase, judge_name: str) -> tuple[bool, str]:
    defendant = world.agents.get(case.defendant)
    if not defendant or not defendant.alive:
        return False, "Defendant is not alive"
    case.status = "in_session"
    case.judge = judge_name
    case.case_file_notes.append(f"{judge_name} summoned {case.defendant} to Supreme Court.")
    defendant.active_court_case_id = case.id
    defendant.location_id = SUPREME_COURT_ID
    world.sync_position(defendant)
    world.log(f"⚖ Court summons: {case.defendant} ordered to Supreme Court (case {case.id})")
    return True, f"{case.defendant} summoned to Supreme Court"


def pass_judgment(
    world: WorldState,
    judge: AgentState,
    case: CourtCase,
    *,
    sentence_type: str,
    reasoning: str,
    jail_hours: float = 0.0,
    community_service_hours: float = 0.0,
) -> tuple[bool, str]:
    defendant = world.agents.get(case.defendant)
    if not defendant:
        return False, "Defendant not found"
    st = sentence_type.strip().lower()
    reasoning = reasoning.strip()
    if not reasoning:
        return False, "reasoning required — cite Singapore law and empathy for the accused"
    if st not in ("death", "jail", "community_service", "acquittal", "warning", "dismissed"):
        return False, "Invalid sentence_type"

    case.judge = judge.name
    case.reasoning = reasoning[:3000]
    case.sentence_type = st
    case.verdict = st
    case.jail_hours = jail_hours
    case.community_service_hours = community_service_hours

    for c in world.data.complaints:
        if c.id == case.complaint_id:
            c.status = "adjudicated"
            break

    if st in ("acquittal", "warning", "dismissed"):
        case.status = "acquittal" if st == "acquittal" else "dismissed"
        case.enforcement_passed = _format_enforcement_passed(case)
        case.case_file_notes.append(f"Closed: {st}.")
        defendant.active_court_case_id = None
        world.log(f"⚖ Case {case.id}: {case.defendant} — {st}. {reasoning[:120]}")
        return True, f"Case closed: {st}"

    if not defendant.alive:
        case.status = "sentenced"
        case.enforcement_passed = _format_enforcement_passed(case)
        return True, "Defendant already deceased"

    if st == "death":
        case.status = "sentenced"
        case.enforcement_passed = _format_enforcement_passed(case)
        case.case_file_notes.append("Death sentence carried out.")
        defendant.active_court_case_id = None
        world.kill_agent(defendant, cause="justice")
        world.log(f"☠ Justice: {defendant.name} sentenced to death — case {case.id}")
        return True, f"{defendant.name} sentenced to death"

    if st == "jail":
        hours = max(2.0, float(jail_hours or 8.0))
        case.status = "sentenced"
        case.enforcement_passed = _format_enforcement_passed(case)
        case.case_file_notes.append(f"Jail sentence: {hours:.0f} sim-hours.")
        defendant.active_court_case_id = None
        defendant.jailed_until = time.time() + sim_hours_to_seconds(hours)
        defendant.location_id = CHANGI_PRISON_ID
        world.sync_position(defendant)
        world.log(
            f"🔒 {defendant.name} sentenced to {hours:.0f} sim-hours at Changi (case {case.id})"
        )
        return True, f"Jail: {hours:.0f} sim-hours at Changi Prison"

    if st == "community_service":
        hours = max(4.0, float(community_service_hours or 12.0))
        case.status = "sentenced"
        case.enforcement_passed = _format_enforcement_passed(case)
        case.case_file_notes.append(f"Community service: {hours:.0f} sim-hours.")
        defendant.active_court_case_id = None
        defendant.community_service_hours = hours
        defendant.jailed_until = None
        world.log(
            f"🧹 {defendant.name} sentenced to {hours:.0f} sim-hours community service (case {case.id})"
        )
        return True, f"Community service: {hours:.0f} sim-hours remaining"

    return False, "Unhandled sentence type"
