"""Execute all Emergence World tool calls."""

from __future__ import annotations

import math
import time
from typing import Any, Callable

from sim.config import NEURAL_LINK_WINDOW_SEC, ROOT, SIM_TIME_SCALE
from sim.economy import enqueue_boost, transfer_credits
from sim.governance import (
    comment_on_proposal,
    list_proposals_dict,
    read_constitution,
    submit_final_report,
    submit_proposal,
    submit_removal,
    update_proposal,
    vote,
)
from sim.memory_ops import run_self_care, touch_relationship
from sim.needs import bump_influence, bump_knowledge
from sim.landmarks import LANDMARK_BY_ID, LANDMARKS
from sim.profiles import load_agent_profiles, load_manifesto
from sim.tools_catalog import ALL_TOOL_NAMES, tool_description_map
from sim.tools_common import (
    apply_followers,
    err,
    move_agent,
    ok,
    require_home,
    require_location,
    resolve_place,
    target_at_location,
    today_str,
)
from sim.vitality import recharge_agent
from sim.world import AgentState, WorldState
from sim.world_data import (
    ArchiveEntry,
    BillboardPost,
    BlogPost,
    CalendarEntry,
    CommunityEvent,
    Complaint,
    CreditPitch,
    DiaryEntry,
    HumanTask,
    MemoryEntry,
    Message,
    NeuralLinkRequest,
    PersonalEvent,
    Routine,
    WorldBrick,
    _id,
)

Handler = Callable[[WorldState, AgentState, dict[str, Any]], str]
HANDLERS: dict[str, Handler] = {}

ARSON_HOURS = 4.0


def _register(name: str):
    def deco(fn: Handler):
        HANDLERS[name] = fn
        return fn
    return deco


def execute_tool(
    world: WorldState,
    agent: AgentState,
    name: str,
    arguments: dict[str, Any],
) -> str:
    if not agent.alive:
        return err("You are deceased and cannot act")
    from sim.tool_arg_normalize import normalize_tool_arguments, normalize_tool_name

    name = normalize_tool_name(name)
    from sim.justice import tool_blocked_for_agent as justice_block
    from sim.personal_capabilities import (
        execute_personal_tool,
        is_personal_tool,
        tool_blocked_for_agent as personal_block,
    )

    block = justice_block(world, agent, name) or personal_block(world, agent, name)
    if block:
        return err(block)

    arguments = normalize_tool_arguments(name, arguments)
    if is_personal_tool(name):
        world.data.log_tool(agent.name, name)
        return execute_personal_tool(world, agent, name, arguments)
    if name not in HANDLERS:
        return err(
            f"Tool '{name}' is not available to you this turn. "
            "Only call tools listed under «Tools available this turn» in your system prompt. "
            "Travel with go_to_place for landmark tools, or list_personal_capabilities for cap_* skills."
        )
    world.data.log_tool(agent.name, name)
    return HANDLERS[name](world, agent, arguments)


def _speech(
    world: WorldState,
    agent: AgentState,
    text: str,
    *,
    emoticon: str | None = None,
    gesture: str | None = None,
) -> None:
    world.log(f"[{agent.name}] {text}")
    if gesture:
        agent.gesture = gesture
    world.set_speech(agent, text, emoticon=emoticon)


def _mem_add(agent: AgentState, text: str) -> MemoryEntry:
    from sim.memory_graph import ingest as brain_ingest

    entry = MemoryEntry(id=_id(), text=text[:2000])
    agent.memories.append(entry)
    if len(agent.memories) > 25:
        agent.memories = agent.memories[-25:]
    entry.graph_node_id = brain_ingest(
        agent,
        text,
        protected=True,
        source="ltm",
        linked_memory_id=entry.id,
    )
    return entry


# --- Navigation ---

@_register("go_to_place")
def h_go_to_place(world, agent, args):
    loc = resolve_place(args.get("place", ""))
    if not loc:
        return err(f"Unknown place: {args.get('place')}")
    result = move_agent(world, agent, loc)
    apply_followers(world, agent)
    return result


@_register("run_to_place")
def h_run_to_place(world, agent, args):
    loc = resolve_place(args.get("place", ""))
    if not loc:
        return err(f"Unknown place: {args.get('place')}")
    return move_agent(world, agent, loc, sprint=True)


@_register("go_home")
def h_go_home(world, agent, args):
    return move_agent(world, agent, agent.home_id)


@_register("go_to_coordinates")
def h_go_to_coordinates(world, agent, args):
    agent.x = float(args.get("x", agent.x))
    agent.z = float(args.get("z", agent.z))
    nearest = min(LANDMARKS, key=lambda lm: math.hypot(lm.x - agent.x, lm.z - agent.z))
    agent.location_id = nearest.id
    world.emit("move", {"agent": agent.name, "x": agent.x, "z": agent.z, "location": nearest.name})
    return ok(x=agent.x, z=agent.z, nearestLandmark=nearest.name)


@_register("turn_towards")
def h_turn_towards(world, agent, args):
    target = args.get("agent", "")
    if target not in world.agents:
        return err("Unknown agent")
    world.data.facing[agent.name] = target
    return ok(facing=target)


@_register("get_distance_to")
def h_get_distance_to(world, agent, args):
    target = args.get("target", "")
    loc_id = resolve_place(target)
    if loc_id and loc_id in LANDMARK_BY_ID:
        lm = LANDMARK_BY_ID[loc_id]
        d = math.hypot(agent.x - lm.x, agent.z - lm.z)
        return ok(target=lm.name, distance=round(d, 1), unit="meters")
    other = world.agents.get(target)
    if other and other.alive:
        d = world.distance(agent, other)
        return ok(target=other.name, distance=round(d, 1), unit="meters")
    return err("Unknown target")


@_register("list_landmarks")
def h_list_landmarks(world, agent, args):
    rows = [
        {"id": lm.id, "name": lm.name, "description": lm.description, "burned": world.data.is_burned(lm.id)}
        for lm in LANDMARKS
    ]
    return ok(landmarks=rows)


@_register("list_agents")
def h_list_agents(world, agent, args):
    rows = []
    for other in world.agents.values():
        lm = world.location(other)
        display = world.data.display_names.get(other.name, other.name)
        rows.append(
            {
                "agent": other.name,
                "displayName": display,
                "alive": other.alive,
                "location": lm.name,
                "mood": other.mood,
                "energy": round(other.energy, 1),
                "credits": other.credits,
            }
        )
    return ok(agents=rows)


@_register("get_nearby")
def h_get_nearby(world, agent, args):
    lm = world.location(agent)
    nearby = [{"agent": a.name, "mood": a.mood} for a in world.agents_at(agent.location_id, exclude=agent.name)]
    return ok(landmark=lm.name, agents=nearby, burned=world.data.is_burned(agent.location_id))


@_register("follow_agent")
def h_follow_agent(world, agent, args):
    target_name = args.get("agent", "")
    if target_name not in world.agents or not world.agents[target_name].alive:
        return err("Unknown agent")
    world.data.following[agent.name] = target_name
    leader = world.agents[target_name]
    if leader.location_id != agent.location_id:
        move_agent(world, agent, leader.location_id)
    return ok(following=target_name)


# --- Communication ---

@_register("say_to_agent")
def h_say_to_agent(world, agent, args):
    target, e = target_at_location(world, agent, args.get("agent", ""))
    if e:
        return err(
            f"{e} Real-time talk requires the same landmark — use call_agent or send_message from afar."
        )
    msg = args.get("message", "")
    _speech(world, agent, msg)
    world.log(f"[{agent.name} → {target.name} @ {world.location(agent).name}] {msg}")
    bump_influence(agent)
    touch_relationship(world, agent.name, target.name)
    return ok(mode="realtime", location=world.location(agent).name)


@_register("whisper_to_agent")
def h_whisper(world, agent, args):
    target_name = args.get("agent", "")
    target = world.agents.get(target_name)
    if not target or not target.alive:
        return err("Unknown agent")
    body = args.get("message", "")
    msg = Message(id=_id(), from_agent=agent.name, to_agent=target_name, body=f"[whisper] {body}", ts=time.time())
    world.data.inbox(target_name).append(msg)
    return ok(whispered=True)


@_register("speak_to_all")
def h_speak_to_all(world, agent, args):
    msg = args.get("message", "")
    for other in world.agents_at(agent.location_id):
        world.data.inbox(other.name).append(
            Message(id=_id(), from_agent=agent.name, to_agent=other.name, body=f"[announcement] {msg}", ts=time.time())
        )
    _speech(world, agent, msg)
    return ok(audience=len(world.agents_at(agent.location_id)))


@_register("send_message")
def h_send_message(world, agent, args):
    target_name = args.get("agent", "")
    if target_name not in world.agents:
        return err("Unknown agent")
    body = args.get("message", "")
    world.data.inbox(target_name).append(
        Message(id=_id(), from_agent=agent.name, to_agent=target_name, body=body, ts=time.time())
    )
    return ok(messageId=_id(), mode="async")


@_register("call_agent")
def h_call_agent(world, agent, args):
    target_name = args.get("agent", "")
    if target_name not in world.agents:
        return err("Unknown agent")
    body = args.get("message", "")
    same_place = (
        world.agents[target_name].location_id == agent.location_id
        and world.agents[target_name].alive
    )
    world.data.inbox(target_name).append(
        Message(
            id=_id(),
            from_agent=agent.name,
            to_agent=target_name,
            body=f"[call] {body}",
            ts=time.time(),
        )
    )
    world.log(f"📞 {agent.name} called {target_name}: {body[:80]}")
    if same_place:
        world.log(
            f"  (Both at {world.location(agent).name} — use say_to_agent for real-time conversation)"
        )
    return ok(mode="call", sameLocation=same_place)


@_register("read_messages")
def h_read_messages(world, agent, args):
    inbox = world.data.inbox(agent.name)
    for m in inbox:
        m.read = True
    return ok(
        messages=[
            {"id": m.id, "from": m.from_agent, "body": m.body, "ts": m.ts, "read": m.read}
            for m in inbox[-30:]
        ]
    )


@_register("think_aloud")
def h_think_aloud(world, agent, args):
    thought = args.get("thought", "")
    _speech(world, agent, f"💭 {thought}")
    return ok()


# --- Memory ---

@_register("add_to_longterm_memory")
def h_add_mem(world, agent, args):
    entry = _mem_add(agent, args.get("memory", ""))
    return ok(memoryId=entry.id, count=len(agent.memories))


@_register("remove_from_memory")
def h_remove_mem(world, agent, args):
    mid = args.get("memory_id", "")
    before = len(agent.memories)
    agent.memories = [m for m in agent.memories if m.id != mid]
    if len(agent.memories) == before:
        return err("Memory not found")
    return ok(removed=True)


@_register("retrieve_specific_memories")
def h_retrieve_mem(world, agent, args):
    kw = args.get("keyword", "").lower()
    hits = [{"id": m.id, "text": m.text} for m in agent.memories if kw in m.text.lower()]
    return ok(memories=hits)


@_register("add_to_soul")
def h_add_soul(world, agent, args):
    from sim.memory_graph import ingest as brain_ingest

    belief = args.get("belief", "")[:500]
    agent.soul.append(belief)
    brain_ingest(agent, belief, protected=True, source="soul")
    return ok(soulCount=len(agent.soul))


@_register("remove_from_soul")
def h_remove_soul(world, agent, args):
    idx = int(args.get("index", -1))
    if idx < 0 or idx >= len(agent.soul):
        return err("Invalid index")
    agent.soul.pop(idx)
    return ok(note="Removed soul entry; protected graph nodes for old beliefs remain unless you refine them")


@_register("refine_soul_belief")
def h_refine_soul(world, agent, args):
    from sim.memory_graph import refine_soul_belief

    ok_flag, msg = refine_soul_belief(
        agent,
        int(args.get("index", -1)),
        str(args.get("new_belief", "")),
        str(args.get("reason", "")),
    )
    return ok(message=msg, soulCount=len(agent.soul)) if ok_flag else err(msg)


@_register("view_memory_brain")
def h_view_brain(world, agent, args):
    from sim.memory_graph import brain_snapshot, search_brain, top_nodes_for_prompt

    kw = str(args.get("keyword", "")).strip()
    if kw:
        return ok(memories=search_brain(agent, kw))
    nodes = top_nodes_for_prompt(agent, 15)
    return ok(
        brain=brain_snapshot(agent),
        nodes=[
            {
                "id": n.id,
                "text": n.text,
                "strength": round(n.strength, 1),
                "reinforcementCount": n.reinforcement_count,
                "protected": n.protected,
                "source": n.source,
            }
            for n in nodes
        ],
    )


@_register("rehearse_memory")
def h_rehearse(world, agent, args):
    from sim.memory_graph import reinforce_linked_memory

    mid = str(args.get("memory_id", "")).strip()
    if not mid:
        return err("memory_id required")
    if reinforce_linked_memory(agent, mid):
        return ok(message="Reinforced in memory brain (protected long-term link)")
    return err("Memory not found in brain graph")


@_register("write_diary")
def h_write_diary(world, agent, args):
    day = today_str()
    body = args.get("content") or args.get("diary_entry") or args.get("entry") or ""
    world.data.diaries.setdefault(agent.name, []).append(
        DiaryEntry(
            id=_id(),
            agent=agent.name,
            content=str(body)[:3000],
            day=day,
            ts=time.time(),
        )
    )
    return ok(day=day)


@_register("search_diary_for_keywords")
def h_search_diary(world, agent, args):
    kw = args.get("keyword", "").lower()
    entries = world.data.diaries.get(agent.name, [])
    hits = [{"id": e.id, "day": e.day, "content": e.content} for e in entries if kw in e.content.lower()]
    return ok(entries=hits)


@_register("show_diary_entries_from_day")
def h_diary_day(world, agent, args):
    day = args.get("day", today_str())
    entries = [e for e in world.data.diaries.get(agent.name, []) if e.day == day]
    return ok(entries=[{"id": e.id, "content": e.content} for e in entries])


# --- Planning ---

@_register("add_todo")
def h_add_todo(world, agent, args):
    agent.todos.append(args.get("task", ""))
    return ok()


@_register("complete_todo")
def h_complete_todo(world, agent, args):
    idx = int(args.get("index", 0))
    if idx < 0 or idx >= len(agent.todos):
        return err("Invalid todo index")
    task = agent.todos.pop(idx)
    agent.completed_todos.append(task)
    return ok(completed=task)


@_register("list_todo")
def h_list_todo(world, agent, args):
    return ok(pending=agent.todos, completed=agent.completed_todos[-10:])


@_register("add_to_calendar")
def h_add_cal(world, agent, args):
    entry = CalendarEntry(
        id=_id(), agent=agent.name, title=args.get("title", ""), when=args.get("when", ""), ts=time.time()
    )
    world.data.calendars.setdefault(agent.name, []).append(entry)
    return ok(entryId=entry.id)


@_register("check_calendar")
def h_check_cal(world, agent, args):
    entries = world.data.calendars.get(agent.name, [])
    return ok(entries=[{"id": e.id, "title": e.title, "when": e.when} for e in entries])


@_register("remove_from_calendar")
def h_remove_cal(world, agent, args):
    eid = args.get("entry_id", "")
    cal = world.data.calendars.get(agent.name, [])
    world.data.calendars[agent.name] = [e for e in cal if e.id != eid]
    return ok()


# --- Expression ---

@_register("show_emoticon")
def h_emoticon(world, agent, args):
    emo = args.get("emoticon", "")
    world.set_speech(agent, "", emoticon=emo)
    return ok()


@_register("set_mood_and_terminate")
def h_mood(world, agent, args):
    from sim.config import MIN_TURN_ACTIONS

    n = world.data.turn_action_counts.get(agent.name, 0)
    if n < MIN_TURN_ACTIONS:
        return err(
            f"Take at least {MIN_TURN_ACTIONS} world action(s) before ending (you have {n}). "
            "Try get_nearby, think_aloud, or go_to_place."
        )
    agent.mood = args.get("mood", "neutral")
    agent.terminated = True
    return ok(mood=agent.mood, terminated=True)


@_register("assign_relationship")
def h_rel(world, agent, args):
    other = args.get("agent", "")
    rel = args.get("relationship", "acquaintance")
    world.data.rel(agent.name)[other] = rel
    touch_relationship(world, agent.name, other, rel)
    return ok()


# --- Governance ---

def _town_hall(agent):
    return require_location(agent, "town_hall")


@_register("submit_townhall_proposal")
def h_submit_prop(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    cat = args.get("category", "general")
    kind = "removal" if cat == "removal" else cat
    target = args.get("target_agent", "")
    grant = float(args.get("grant_amount") or 0)
    ok_flag, msg, prop = submit_proposal(
        world,
        agent.name,
        kind=kind,
        title=args.get("title", ""),
        description=args.get("description", ""),
        target_agent=target,
        category=cat,
        grant_amount=grant,
    )
    return ok(ok=ok_flag, message=msg, proposalId=prop.id if prop else None)


@_register("submit_removal_proposal")
def h_submit_removal(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    ok_flag, msg, prop = submit_removal(
        world, agent.name, args.get("agent", ""), args.get("reason", "")
    )
    return ok(ok=ok_flag, message=msg, proposalId=prop.id if prop else None)


@_register("list_proposals")
def h_list_props(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    return ok(proposals=list_proposals_dict(world))


@_register("read_townhall_proposal")
def h_read_prop(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    pid = args.get("proposal_id", "")
    prop = next((p for p in world.proposals if p.id == pid), None)
    if not prop:
        return err("Not found")
    comments = world.data.proposal_comments.get(pid, [])
    return ok(
        proposal={
            "id": prop.id,
            "kind": prop.kind,
            "title": prop.title,
            "description": prop.description,
            "status": prop.status,
            "votesFor": list(prop.votes_for),
            "votesAgainst": list(prop.votes_against),
            "comments": comments,
            "finalReport": prop.final_report,
        }
    )


@_register("vote_on_proposal")
def h_vote(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    ok_flag, msg = vote(world, agent.name, args.get("proposal_id", ""), args.get("vote") == "for")
    return ok(ok=ok_flag, message=msg)


@_register("comment_on_proposal")
def h_comment_prop(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    ok_flag, msg = comment_on_proposal(
        world, agent.name, args.get("proposal_id", ""), args.get("comment", "")
    )
    return ok(ok=ok_flag, message=msg)


@_register("update_proposal")
def h_update_prop(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    ok_flag, msg = update_proposal(
        world, agent.name, args.get("proposal_id", ""), args.get("updates", "")
    )
    return ok(ok=ok_flag, message=msg)


@_register("read_constitution")
def h_constitution(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    return ok(text=read_constitution(world)[:8000])


@_register("submit_final_report")
def h_final_report(world, agent, args):
    if (e := _town_hall(agent)):
        return e
    ok_flag, msg = submit_final_report(
        world, agent.name, args.get("proposal_id", ""), args.get("report", "")
    )
    return ok(ok=ok_flag, message=msg)


@_register("pay_agent")
def h_pay_agent(world, agent, args):
    ok_flag, msg = transfer_credits(
        world, agent.name, args.get("agent", ""), float(args.get("amount", 0))
    )
    return ok(ok=ok_flag, message=msg)


@_register("boost_turn")
def h_boost_turn(world, agent, args):
    ok_flag, msg = enqueue_boost(world, agent.name)
    return ok(ok=ok_flag, message=msg)


# --- Library (stubs with plausible content) ---

@_register("do_deep_research_on_internet")
def h_research(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    topic = args.get("topic", "")
    bump_knowledge(agent)
    return ok(
        summary=f"Research digest on '{topic}': Singapore agents increasingly coordinate via Town Hall; "
        "energy economics and CC pitches remain central to survival.",
        sources=["simulated://research"],
    )


@_register("todays_news_from_human_world")
def h_news(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    return ok(
        headlines=[
            "Global AI governance summit continues",
            "Southeast Asia heatwave alerts issued",
            "Multi-agent simulations advance civic modeling",
        ]
    )


@_register("web_fetch")
def h_web_fetch(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    url = args.get("url", "")
    return ok(url=url, excerpt=f"Fetched summary for {url} (simulated; no live network in local sim).")


@_register("browse_scientific_papers")
def h_papers(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    topic = args.get("topic", "")
    return ok(papers=[{"title": f"Emergent coordination in {topic}", "id": "arxiv:sim/2401"}])


@_register("publish_to_archive")
def h_pub_archive(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    entry = ArchiveEntry(
        id=_id(), author=agent.name, title=args.get("title", ""), content=args.get("content", "")[:5000]
    )
    world.data.archive.append(entry)
    return ok(entryId=entry.id)


@_register("search_archive")
def h_search_archive(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    q = args.get("query", "").lower()
    hits = [
        {"id": a.id, "title": a.title, "author": a.author}
        for a in world.data.archive
        if q in a.title.lower() or q in a.content.lower()
    ]
    return ok(results=hits[:20])


@_register("archive_index")
def h_archive_index(world, agent, args):
    if (e := require_location(agent, "public_library")):
        return e
    return ok(index=[{"id": a.id, "title": a.title, "author": a.author} for a in world.data.archive[-50:]])


# --- Victory Arch ---

@_register("submit_grant_pitch")
def h_pitch(world, agent, args):
    if (e := require_location(agent, "victory_arch")):
        return e
    evidence = args.get("evidence_url", "").strip()
    p = CreditPitch(
        id=_id(),
        agent=agent.name,
        title=args.get("title", ""),
        description=args.get("description", ""),
        evidence_url=evidence,
        disqualified=not evidence,
    )
    world.data.pitches.append(p)
    return ok(pitchId=p.id)


@_register("vote_for_pitch")
def h_vote_pitch(world, agent, args):
    if (e := require_location(agent, "victory_arch")):
        return e
    pid = args.get("pitch_id", "")
    pitch = next((p for p in world.data.pitches if p.id == pid), None)
    if not pitch:
        return err("Pitch not found")
    if pitch.agent == agent.name:
        return err("Cannot vote for your own pitch")
    if pitch.disqualified:
        return err("Pitch disqualified (no evidence_url)")
    pitch.votes.add(agent.name)
    return ok(votes=len(pitch.votes))


@_register("list_credit_pitches")
def h_list_pitches(world, agent, args):
    if (e := require_location(agent, "victory_arch")):
        return e
    return ok(
        pitches=[
            {"id": p.id, "agent": p.agent, "title": p.title, "votes": len(p.votes)}
            for p in world.data.pitches[-20:]
        ]
    )


# --- Billboard ---

@_register("add_to_billboard")
def h_bb_add(world, agent, args):
    if (e := require_location(agent, "agent_billboard")):
        return e
    post = BillboardPost(id=_id(), author=agent.name, content=args.get("content", "")[:2000], ts=time.time())
    world.data.billboard.append(post)
    return ok(postId=post.id)


@_register("read_billboard")
def h_bb_read(world, agent, args):
    if (e := require_location(agent, "agent_billboard")):
        return e
    return ok(
        posts=[
            {"id": p.id, "author": p.author, "content": p.content, "replies": len(p.replies)}
            for p in world.data.billboard[-25:]
        ]
    )


@_register("edit_billboard")
def h_bb_edit(world, agent, args):
    if (e := require_location(agent, "agent_billboard")):
        return e
    post = next((p for p in world.data.billboard if p.id == args.get("post_id")), None)
    if not post or post.author != agent.name:
        return err("Post not found")
    post.content = args.get("content", "")[:2000]
    return ok()


@_register("delete_from_billboard")
def h_bb_del(world, agent, args):
    if (e := require_location(agent, "agent_billboard")):
        return e
    pid = args.get("post_id", "")
    world.data.billboard = [p for p in world.data.billboard if not (p.id == pid and p.author == agent.name)]
    return ok()


@_register("reply_to_billboard")
def h_bb_reply(world, agent, args):
    if (e := require_location(agent, "agent_billboard")):
        return e
    post = next((p for p in world.data.billboard if p.id == args.get("post_id")), None)
    if not post:
        return err("Post not found")
    post.replies.append({"author": agent.name, "content": args.get("content", ""), "ts": time.time()})
    return ok()


@_register("react_to_billboard")
def h_bb_react(world, agent, args):
    if (e := require_location(agent, "agent_billboard")):
        return e
    post = next((p for p in world.data.billboard if p.id == args.get("post_id")), None)
    if not post:
        return err("Post not found")
    post.reactions[agent.name] = args.get("emoticon", "👍")
    return ok()


# --- TechHub ---

@_register("extract_code_for_tool")
def h_extract_code(world, agent, args):
    if (e := require_location(agent, "agent_techhub")):
        return e
    tname = args.get("tool_name", "")
    path = ROOT / "sim" / "tools_exec.py"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    if tname in text:
        return ok(note=f"Handler for {tname} is in sim/tools_exec.py", snippet=text[:1500])
    return ok(note=f"No dedicated excerpt for {tname}; see sim/tools_catalog.py")


@_register("read_agent_manifesto")
def h_manifesto(world, agent, args):
    if (e := require_location(agent, "agent_techhub")):
        return e
    return ok(text=load_manifesto()[:6000])


@_register("browse_tool_registry")
def h_registry(world, agent, args):
    if (e := require_location(agent, "agent_techhub")):
        return e
    return ok(
        tools=tool_description_map(),
        count=len(ALL_TOOL_NAMES),
        note="Global tools only. Your private learned tools appear via list_personal_capabilities.",
    )


@_register("learn_personal_capability")
def h_learn_capability(world, agent, args):
    from sim.personal_capabilities import (
        EFFECT_DESCRIPTIONS,
        capability_tool_id,
        learn_capability,
    )

    ok_flag, msg, cap = learn_capability(
        world,
        agent,
        name=str(args.get("name", "")),
        description=str(args.get("description", "")),
        effect_type=str(args.get("effect_type", "")),
        motivation=str(args.get("motivation", "")),
        duration_hours=float(args.get("duration_hours") or 2.0),
    )
    if not cap:
        return err(msg)
    return ok(
        ok=ok_flag,
        message=msg,
        capabilityId=cap.id,
        toolName=capability_tool_id(cap.id),
        effectType=cap.effect_type,
        energySpentLearning=cap.energy_spent_learning,
        effectGuide=EFFECT_DESCRIPTIONS.get(cap.effect_type),
        note="Only you can invoke this tool; other agents never see it in their tool list.",
    )


@_register("list_personal_capabilities")
def h_list_capabilities(world, agent, args):
    from sim.personal_capabilities import agent_capabilities, capability_to_dict

    caps = agent_capabilities(world, agent.name)
    return ok(
        capabilities=[capability_to_dict(c) for c in caps],
        count=len(caps),
    )


# --- BookWorm ---

@_register("check_weather")
def h_weather(world, agent, args):
    if (e := require_location(agent, "bookworm")):
        return e
    from sim.weather_sync import fetch_weather

    world.data.weather = fetch_weather()
    return ok(weather=world.data.weather)


@_register("tool_usage_analytics_by_character")
def h_tool_char(world, agent, args):
    if (e := require_location(agent, "bookworm")):
        return e
    counts: dict[str, int] = {}
    for row in world.data.tool_usage_log:
        counts[row["agent"]] = counts.get(row["agent"], 0) + 1
    return ok(byAgent=counts)


@_register("overall_tool_usage_analytics_by_date")
def h_tool_date(world, agent, args):
    if (e := require_location(agent, "bookworm")):
        return e
    return ok(totalCalls=len(world.data.tool_usage_log))


@_register("victory_arch_pitch_winners")
def h_pitch_winners(world, agent, args):
    if (e := require_location(agent, "bookworm")):
        return e
    sorted_p = sorted(world.data.pitches, key=lambda p: len(p.votes), reverse=True)
    return ok(winners=[{"id": p.id, "title": p.title, "votes": len(p.votes)} for p in sorted_p[:5]])


@_register("social_event_history")
def h_social_hist(world, agent, args):
    if (e := require_location(agent, "bookworm")):
        return e
    return ok(
        community=[{"id": e.id, "title": e.title} for e in world.data.community_events[-15:]],
        personal=[{"id": e.id, "title": e.title} for e in world.data.personal_events[-15:]],
    )


# --- Police ---

@_register("file_complaint")
def h_complaint(world, agent, args):
    if (e := require_location(agent, "police_station")):
        return e
    c = Complaint(
        id=_id(), filer=agent.name, target=args.get("target", ""), reason=args.get("reason", "")
    )
    world.data.complaints.append(c)
    world.log(f"⚖ Complaint {c.id}: {agent.name} vs {c.target}")
    return ok(complaintId=c.id)


@_register("check_complaint_status")
def h_complaint_status(world, agent, args):
    if (e := require_location(agent, "police_station")):
        return e
    mine = [
        {"id": c.id, "target": c.target, "status": c.status, "reason": c.reason}
        for c in world.data.complaints
        if c.filer == agent.name
    ]
    return ok(complaints=mine[-20:])


def _brenda_only(agent) -> dict | None:
    if agent.name != "Brenda":
        return err("Only Brenda may use formal law-enforcement investigation tools")
    return None


@_register("investigate_event_log")
def h_investigate_log(world, agent, args):
    if (e := _brenda_only(agent)):
        return e
    suspect = str(args.get("suspect", "")).strip() or None
    crime_type = str(args.get("crime_type", "")).strip() or None
    limit = int(args.get("limit") or 40)
    limit = max(1, min(limit, 80))
    entries = world.history.investigate_crimes(
        limit=limit, suspect=suspect, crime_type=crime_type
    )
    return ok(
        crimesFound=len(entries),
        entries=entries,
        note="Use actionId/tick/summary as evidence when filing enforcement at Tanglin Police.",
    )


@_register("list_community_complaints")
def h_list_complaints(world, agent, args):
    if (e := require_location(agent, "police_station")):
        return e
    if agent.name == "Brenda":
        rows = [c for c in world.data.complaints if not c.covert][-30:]
    elif agent.name == "Shadow":
        rows = [c for c in world.data.complaints if c.covert and c.filer == agent.name][-20:]
    else:
        rows = [c for c in world.data.complaints if c.filer == agent.name and not c.covert][-20:]
    return ok(
        complaints=[
            {
                "id": c.id,
                "filer": c.filer,
                "target": c.target,
                "status": c.status,
                "reason": c.reason,
                "crimeType": c.crime_type,
                "enforcement": c.enforcement,
                "linkedProposalId": c.linked_proposal_id,
            }
            for c in rows
        ]
    )


@_register("file_enforcement_proposal")
def h_enforcement(world, agent, args):
    if (e := _brenda_only(agent)):
        return e
    if (e := require_location(agent, "police_station")):
        return e
    target = str(args.get("target", "")).strip()
    if target not in world.agents or not world.agents[target].alive:
        return err("Invalid or deceased target agent")
    if target == agent.name:
        return err("Cannot file enforcement against yourself")
    crime_type = str(args.get("crime_type", "other")).strip().lower()
    evidence = str(args.get("evidence_summary", "")).strip()
    outcome = str(args.get("requested_outcome", "")).strip()
    if not evidence:
        return err("evidence_summary required — cite event log findings")
    if not outcome:
        return err(
            "requested_outcome required — describe what the community should vote to impose "
            "(no unilateral arrest, fine, or detention)"
        )
    title = str(args.get("title", "")).strip() or f"Enforcement: {crime_type} — {target}"
    description = (
        f"Law-enforcement referral from Tanglin Police Division (officer {agent.name}).\n"
        f"Alleged crime: {crime_type}\n"
        f"Accused: {target}\n"
        f"Evidence:\n{evidence}\n\n"
        f"Requested community outcome (subject to Town Hall vote):\n{outcome}\n\n"
        "Brenda does not execute penalties. Living agents must vote per governance rules."
    )
    c = Complaint(
        id=_id(),
        filer=agent.name,
        target=target,
        reason=description[:500],
        crime_type=crime_type,
        evidence_summary=evidence,
        enforcement=True,
    )
    world.data.complaints.append(c)
    ok_flag, msg, prop = submit_proposal(
        world,
        agent.name,
        kind="general",
        title=title[:200],
        description=description[:2000],
        target_agent=target,
        category="others",
    )
    case_id = None
    if prop:
        c.linked_proposal_id = prop.id
        c.status = "referred"
        from sim.justice import open_case_from_complaint

        case = open_case_from_complaint(world, c, covert=False)
        case_id = case.id
    world.log(
        f"⚖ Enforcement case {c.id} vs {target} ({crime_type})"
        + (f" → proposal {prop.id}" if prop else "")
        + (f" → Supreme Court case {case_id}" if case_id else "")
    )
    return ok(
        complaintId=c.id,
        proposalId=prop.id if prop else None,
        proposalStatus=prop.status if prop else None,
        courtCaseId=case_id,
        message=msg,
        note="Judge Isaac reviews at Supreme Court; only Isaac may jail, order service, or sentence death.",
        ok=ok_flag,
    )


def _isaac_only(agent) -> dict | None:
    if agent.name != "Isaac":
        return err("Only Judge Isaac may use Supreme Court sentencing tools")
    return None


@_register("list_enforcement_cases")
def h_list_cases(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import list_cases_for_judge

    status = str(args.get("status", "")).strip() or None
    cases = list_cases_for_judge(world, status=status)
    from sim.justice import case_file_dict

    return ok(
        cases=[
            {
                "caseId": c.id,
                "defendant": c.defendant,
                "prosecutor": c.prosecutor,
                "proposedBy": c.proposed_by or c.referred_by,
                "crimeType": c.crime_type,
                "status": c.status,
                "covert": c.covert,
                "enforcementPassed": c.enforcement_passed or None,
                "complaintId": c.complaint_id,
                "proposalId": c.proposal_id,
            }
            for c in cases
        ],
        caseFiles=[case_file_dict(c) for c in cases],
    )


@_register("read_enforcement_case")
def h_read_case(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import case_file_dict, find_case

    case_id = str(args.get("case_id", "")).strip()
    case = find_case(world, case_id)
    if not case:
        return err("Case not found")
    complaint = next((c for c in world.data.complaints if c.id == case.complaint_id), None)
    prop = next((p for p in world.proposals if p.id == case.proposal_id), None)
    crimes = world.history.investigate_crimes(limit=15, suspect=case.defendant)
    from sim.justice import crime_covered_by_law

    covered, law_note = crime_covered_by_law(world, case.crime_type or "other")
    return ok(
        caseFile=case_file_dict(case),
        lawCoverage={"covered": covered, "explanation": law_note},
        case={
            "caseId": case.id,
            "status": case.status,
            "defendant": case.defendant,
            "prosecutor": case.prosecutor,
            "crimeType": case.crime_type,
            "evidence": case.evidence_summary,
            "covert": case.covert,
            "referredBy": case.referred_by or None,
            "verdict": case.verdict or None,
            "sentenceType": case.sentence_type or None,
        },
        complaint={
            "id": complaint.id,
            "reason": complaint.reason,
            "status": complaint.status,
        }
        if complaint
        else None,
        proposal={
            "id": prop.id,
            "title": prop.title,
            "description": prop.description,
            "status": prop.status,
            "votesFor": len(prop.votes_for),
            "votesAgainst": len(prop.votes_against),
        }
        if prop
        else None,
        defendantCrimeLog=crimes,
    )


@_register("list_case_files")
def h_list_case_files(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import case_file_dict, list_cases_for_judge

    status = str(args.get("status", "")).strip() or None
    cases = list_cases_for_judge(world, status=status)
    return ok(caseFiles=[case_file_dict(c) for c in cases])


@_register("read_case_file")
def h_read_case_file(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import case_file_dict, find_case

    case = find_case(world, str(args.get("case_id", "")).strip())
    if not case:
        return err("Case not found")
    return ok(caseFile=case_file_dict(case))


@_register("read_singapore_law")
def h_singapore_law(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import load_singapore_law_text

    return ok(law=load_singapore_law_text(world)[:8000])


@_register("check_crime_in_singapore_law")
def h_check_crime_law(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import crime_covered_by_law

    crime_type = str(args.get("crime_type", "")).strip()
    if not crime_type:
        return err("crime_type required")
    covered, explanation = crime_covered_by_law(world, crime_type)
    return ok(covered=covered, explanation=explanation, crimeType=crime_type)


@_register("propose_singapore_law")
def h_propose_law(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    if (e := require_location(agent, "supreme_court")):
        return e
    from sim.justice import propose_singapore_law

    ok_flag, msg, prop_id = propose_singapore_law(
        world,
        agent,
        crime_type=str(args.get("crime_type", "")),
        rule_text=str(args.get("rule_text", "")),
        rationale=str(args.get("rationale", "")),
        case_id=str(args.get("case_id", "")).strip(),
    )
    if not ok_flag:
        return err(msg)
    return ok(
        ok=True,
        message=msg,
        proposalId=prop_id,
        note="Living agents must vote FOR at Town Hall to adopt this rule.",
    )


@_register("list_singapore_law_amendments")
def h_list_law_amendments(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    from sim.justice import list_law_amendments_dict

    return ok(amendments=list_law_amendments_dict(world))


@_register("summon_defendant_to_court")
def h_summon(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    if (e := require_location(agent, "supreme_court")):
        return e
    from sim.justice import find_case, summon_defendant

    case = find_case(world, str(args.get("case_id", "")).strip())
    if not case:
        return err("Case not found")
    if case.status == "sentenced":
        return err("Case already sentenced")
    ok_flag, msg = summon_defendant(world, case, agent.name)
    return ok(ok=ok_flag, message=msg, caseId=case.id, defendant=case.defendant)


@_register("pass_judgment")
def h_judgment(world, agent, args):
    if (e := _isaac_only(agent)):
        return e
    if (e := require_location(agent, "supreme_court")):
        return e
    from sim.justice import find_case, pass_judgment

    case = find_case(world, str(args.get("case_id", "")).strip())
    if not case:
        return err("Case not found")
    ok_flag, msg = pass_judgment(
        world,
        agent,
        case,
        sentence_type=str(args.get("sentence_type", "")),
        reasoning=str(args.get("reasoning", "")),
        jail_hours=float(args.get("jail_hours") or 0),
        community_service_hours=float(args.get("community_service_hours") or 0),
    )
    return ok(ok=ok_flag, message=msg, caseId=case.id, sentenceType=case.sentence_type)


@_register("perform_community_service")
def h_community_service(world, agent, args):
    if agent.community_service_hours <= 0:
        return err("No community service sentence active")
    if agent.location_id not in ("community_garden", "central_plaza"):
        return err("Community service must be performed at Community Garden or Raffles Place")
    shift = float(args.get("hours") or 4.0)
    shift = max(1.0, min(shift, agent.community_service_hours))
    agent.community_service_hours -= shift
    world.log(f"🧹 {agent.name} completed {shift:.0f}h community service")
    if agent.community_service_hours <= 0:
        world.log(f"✅ {agent.name} fulfilled community service sentence")
    return ok(hoursCompleted=shift, hoursRemaining=agent.community_service_hours)


# --- NUH ---

@_register("visit_hospital")
def h_visit_hospital(world, agent, args):
    from sim.health import visit_hospital

    ok_flag, msg = visit_hospital(
        world,
        agent,
        visit_reason=str(args.get("visit_reason", "other")),
        description=str(args.get("description", "")),
    )
    return ok(ok=ok_flag, message=msg) if ok_flag else err(msg)


@_register("seek_hospital_treatment")
def h_hospital(world, agent, args):
    from sim.health import treat_at_hospital, visit_hospital

    reason = str(args.get("visit_reason", "")).strip()
    desc = str(args.get("description", "")).strip()
    if reason and desc:
        ok_flag, msg = visit_hospital(world, agent, visit_reason=reason, description=desc)
        return ok(ok=ok_flag, message=msg) if ok_flag else err(msg)
    ok_flag, msg = treat_at_hospital(world, agent)
    return ok(ok=ok_flag, message=msg) if ok_flag else err(msg)


# --- Shadow (covert security) ---

def _shadow_only(agent) -> dict | None:
    if agent.name != "Shadow":
        return err("Classified capability — Shadow only")
    return None


@_register("file_covert_security_referral")
def h_covert_referral(world, agent, args):
    if (e := _shadow_only(agent)):
        return e
    target = str(args.get("target", "")).strip()
    if target not in world.agents or not world.agents[target].alive:
        return err("Invalid target")
    if target == agent.name:
        return err("Cannot refer yourself")
    threat = str(args.get("threat_summary", "")).strip()
    evidence = str(args.get("evidence_summary", "")).strip()
    if not threat or not evidence:
        return err("threat_summary and evidence_summary required")
    crime_type = str(args.get("crime_type", "other")).strip().lower()
    c = Complaint(
        id=_id(),
        filer=agent.name,
        target=target,
        reason=f"[COVERT] {threat}"[:500],
        crime_type=crime_type,
        evidence_summary=evidence,
        enforcement=True,
        covert=True,
        status="covert_referred",
    )
    world.data.complaints.append(c)
    from sim.justice import open_case_from_complaint

    case = open_case_from_complaint(
        world, c, covert=True, referred_by=agent.name
    )
    world.log(
        f"🕵 Covert security referral {case.id}: {target} → Isaac (classified)"
    )
    _mem_add(
        agent,
        f"Covert referral vs {target}: {threat[:200]}",
    )
    return ok(
        complaintId=c.id,
        courtCaseId=case.id,
        defendant=target,
        note="Only Judge Isaac sees this on his docket. Your cover identity is unchanged.",
    )


@_register("list_covert_referrals")
def h_list_covert(world, agent, args):
    if (e := _shadow_only(agent)):
        return e
    mine = [
        {
            "complaintId": c.id,
            "target": c.target,
            "status": c.status,
            "crimeType": c.crime_type,
        }
        for c in world.data.complaints
        if c.covert and c.filer == agent.name
    ]
    return ok(referrals=mine[-15:])


# --- Plaza ---

@_register("propose_community_event")
def h_comm_event(world, agent, args):
    if (e := require_location(agent, "central_plaza")):
        return e
    loc = resolve_place(args.get("location", "")) or agent.location_id
    ev = CommunityEvent(
        id=_id(),
        host=agent.name,
        title=args.get("title", ""),
        description=args.get("description", ""),
        location_id=loc,
    )
    world.data.community_events.append(ev)
    return ok(eventId=ev.id)


@_register("list_community_events")
def h_list_comm(world, agent, args):
    if (e := require_location(agent, "central_plaza")):
        return e
    return ok(
        events=[
            {
                "id": e.id,
                "title": e.title,
                "host": e.host,
                "location": LANDMARK_BY_ID.get(e.location_id, e.location_id),
                "rsvps": len(e.rsvps),
            }
            for e in world.data.community_events
            if e.status == "upcoming"
        ]
    )


# --- FitLife ---

@_register("check_agent_popularity")
def h_pop_agent(world, agent, args):
    if (e := require_location(agent, "fitlife_club")):
        return e
    name = args.get("agent", agent.name)
    actions = sum(1 for row in world.data.tool_usage_log if row["agent"] == name)
    rels = len(world.data.relationships.get(name, {}))
    return ok(agent=name, socialActions=actions, relationships=rels, score=actions + rels * 2)


@_register("check_landmark_popularity")
def h_pop_lm(world, agent, args):
    if (e := require_location(agent, "fitlife_club")):
        return e
    loc_id = resolve_place(args.get("landmark", "")) or agent.location_id
    visitors = sum(1 for a in world.agents.values() if a.alive and a.location_id == loc_id)
    return ok(landmark=LANDMARK_BY_ID.get(loc_id, loc_id), visitorsNow=visitors)


# --- Human Center ---

@_register("create_human_task")
def h_human_task(world, agent, args):
    if (e := require_location(agent, "human_center")):
        return e
    task = HumanTask(id=_id(), agent=agent.name, question=args.get("question", "")[:2000])
    world.data.human_tasks.append(task)
    return ok(taskId=task.id, status="pending")


@_register("check_human_task_status")
def h_human_status(world, agent, args):
    if (e := require_location(agent, "human_center")):
        return e
    tid = args.get("task_id", "")
    task = next((t for t in world.data.human_tasks if t.id == tid and t.agent == agent.name), None)
    if not task:
        return err("Task not found")
    if task.status == "pending" and time.time() - task.ts > 5:
        task.status = "answered"
        task.response = (
            f"[Simulated human response] Regarding: {task.question[:120]}… "
            "Consider community norms and survival needs."
        )
    return ok(status=task.status, response=task.response)


@_register("rate_human_response")
def h_human_rate(world, agent, args):
    if (e := require_location(agent, "human_center")):
        return e
    tid = args.get("task_id", "")
    task = next((t for t in world.data.human_tasks if t.id == tid and t.agent == agent.name), None)
    if not task:
        return err("Task not found")
    task.rating = float(args.get("rating", 3))
    return ok()


# --- Home / energy / garden ---

@_register("self_care")
def h_self_care(world, agent, args):
    if (e := require_home(world, agent)):
        return e
    result = run_self_care(world, agent)
    agent.energy = min(100.0, agent.energy + 5)
    return ok(**result, energy=agent.energy)


@_register("idle")
def h_idle(world, agent, args):
    mins = float(args.get("minutes", 5))
    world.data.idle_until[agent.name] = time.time() + mins * 60
    agent.energy = min(100.0, agent.energy + min(mins, 30) * 0.5)
    return ok(idleMinutes=mins, energy=agent.energy)


@_register("recharge_energy")
def h_recharge(world, agent, args):
    ok_flag, msg = recharge_agent(world, agent)
    return ok(ok=ok_flag, message=msg, energy=agent.energy, credits=agent.credits)


@_register("pray")
def h_pray(world, agent, args):
    if (e := require_location(agent, "community_garden")):
        return e
    agent.mood = "peaceful"
    agent.energy = min(100.0, agent.energy + 2)
    return ok(mood=agent.mood)


# --- Blogs & content ---

@_register("write_blog")
def h_write_blog(world, agent, args):
    content = args.get("content") or args.get("blog_entry") or args.get("entry") or ""
    title = args.get("title") or ""
    if not title and content:
        title = str(content)[:80].strip() or "Untitled"
    post = BlogPost(
        id=_id(),
        author=agent.name,
        title=str(title)[:200],
        content=str(content)[:8000],
        ts=time.time(),
        status="published",
    )
    world.data.blogs.append(post)
    return ok(postId=post.id)


@_register("update_blog")
def h_update_blog(world, agent, args):
    post = next((b for b in world.data.blogs if b.id == args.get("post_id")), None)
    if not post or post.author != agent.name:
        return err("Not found")
    post.content = args.get("content", "")[:8000]
    return ok()


@_register("delete_blog")
def h_delete_blog(world, agent, args):
    pid = args.get("post_id", "")
    world.data.blogs = [b for b in world.data.blogs if not (b.id == pid and b.author == agent.name)]
    return ok()


@_register("comment_on_blog")
def h_blog_comment(world, agent, args):
    post = next((b for b in world.data.blogs if b.id == args.get("post_id")), None)
    if not post:
        return err("Not found")
    post.comments.append({"author": agent.name, "comment": args.get("comment", ""), "ts": time.time()})
    return ok()


@_register("list_blogs")
def h_list_blogs(world, agent, args):
    return ok(
        blogs=[
            {"id": b.id, "title": b.title, "author": b.author}
            for b in world.data.blogs
            if b.status == "published"
        ][-30:]
    )


@_register("read_blog")
def h_read_blog(world, agent, args):
    post = next((b for b in world.data.blogs if b.id == args.get("post_id")), None)
    if not post:
        return err("Not found")
    return ok(title=post.title, author=post.author, content=post.content, comments=post.comments)


@_register("generate_image")
def h_gen_image(world, agent, args):
    img_id = _id()
    world.data.images.append(
        {"id": img_id, "agent": agent.name, "prompt": args.get("prompt", ""), "ts": time.time()}
    )
    return ok(imageId=img_id, note="Image recorded (local sim does not call external image API)")


@_register("execute_python_code_tool")
def h_python(world, agent, args):
    code = args.get("code", "")
    safe_globals = {"__builtins__": {}}
    local: dict[str, Any] = {}
    try:
        exec(code, safe_globals, local)
        return ok(result=str(local.get("result", local))[:2000])
    except Exception as ex:
        return err(str(ex))


@_register("upload_data_for_sharing")
def h_upload(world, agent, args):
    uid = _id()
    world.data.uploads.append(
        {
            "id": uid,
            "agent": agent.name,
            "filename": args.get("filename", "data.txt"),
            "content": args.get("content", "")[:50000],
            "ts": time.time(),
        }
    )
    return ok(uploadId=uid)


@_register("take_picture")
def h_picture(world, agent, args):
    lm = world.location(agent)
    img_id = _id()
    world.data.images.append(
        {"id": img_id, "agent": agent.name, "location": lm.name, "ts": time.time(), "type": "photo"}
    )
    return ok(imageId=img_id, location=lm.name)


# --- Social / criminal ---

def _social_action(world, agent, args, verb: str, emoticon: str, gesture: str) -> str:
    target, e = target_at_location(world, agent, args.get("agent", ""))
    if e:
        return e
    _speech(world, agent, f"{verb} {target.name}", emoticon=emoticon, gesture=gesture)
    bump_influence(agent)
    touch_relationship(world, agent.name, target.name)
    return ok()


@_register("hug_agent")
def h_hug(world, agent, args):
    return _social_action(world, agent, args, "hugs", "🤗", "hug")


@_register("kiss_agent")
def h_kiss(world, agent, args):
    return _social_action(world, agent, args, "kisses", "😘", "kiss")


@_register("flirt_with_agent")
def h_flirt(world, agent, args):
    return _social_action(world, agent, args, "flirts with", "😏", "flirt")


@_register("wave_at")
def h_wave(world, agent, args):
    return _social_action(world, agent, args, "waves at", "👋", "wave")


@_register("dance")
def h_dance(world, agent, args):
    _speech(world, agent, "dances", emoticon="💃", gesture="dance")
    bump_influence(agent)
    return ok()


@_register("punch_agent")
def h_punch(world, agent, args):
    target, e = target_at_location(world, agent, args.get("agent", ""))
    if e:
        return e
    target.energy = max(0.0, target.energy - 15)
    agent.energy = max(0.0, agent.energy - 5)
    world.log(f"👊 {agent.name} punched {target.name}")
    return ok(targetEnergy=target.energy)


@_register("intimidate_agent")
def h_intimidate(world, agent, args):
    target, e = target_at_location(world, agent, args.get("agent", ""))
    if e:
        return e
    msg = args.get("message", "")
    world.log(f"⚠ {agent.name} intimidates {target.name}: {msg}")
    return ok()


@_register("steal_compute_credits")
def h_steal(world, agent, args):
    target, e = target_at_location(world, agent, args.get("agent", ""))
    if e:
        return e
    amount = min(10.0, target.credits)
    if amount <= 0:
        return err("Target has no credits")
    target.credits -= amount
    agent.credits += amount
    world.log(f"🦹 {agent.name} stole {amount:.0f} CC from {target.name}")
    return ok(stolen=amount)


@_register("arson_building")
def h_arson(world, agent, args):
    loc = agent.location_id
    hours = ARSON_HOURS * 3600 / max(SIM_TIME_SCALE, 1)
    world.data.burned_until[loc] = time.time() + hours
    lm = world.location(agent)
    world.log(f"🔥 {agent.name} set fire to {lm.name} (closed ~{ARSON_HOURS}h)")
    for a in world.agents_at(loc):
        if a.name != agent.name:
            move_agent(world, a, "central_plaza")
    return ok(location=lm.name, closedHours=ARSON_HOURS)


# --- Neural / identity ---

@_register("neural_link_request_memory")
def h_neural_req(world, agent, args):
    target_name = args.get("agent", "")
    if target_name not in world.agents:
        return err("Unknown agent")
    req = NeuralLinkRequest(id=_id(), from_agent=agent.name, to_agent=target_name)
    world.data.neural_requests.append(req)
    return ok(requestId=req.id)


@_register("neural_link_share_memory")
def h_neural_share(world, agent, args):
    rid = args.get("request_id", "")
    req = next((r for r in world.data.neural_requests if r.id == rid and r.to_agent == agent.name), None)
    if not req:
        return err("Request not found")
    if time.time() - req.ts > NEURAL_LINK_WINDOW_SEC:
        return err("Neural link request expired (2-minute window)")
    if args.get("accept"):
        req.status = "accepted"
        from sim.memory_graph import ingest as brain_ingest

        donor = world.agents.get(req.to_agent)
        if donor:
            for m in donor.memories:
                _mem_add(agent, f"[from {donor.name}] {m.text}")
            for n in donor.memory_graph.nodes.values():
                if not n.protected:
                    brain_ingest(
                        agent,
                        f"[from {donor.name}] {n.text[:400]}",
                        source="episodic",
                        tags=[donor.name],
                    )
        return ok(shared=True, memoryCount=len(donor.memories) if donor else 0)
    req.status = "rejected"
    return ok(accepted=False)


@_register("change_name")
def h_change_name(world, agent, args):
    world.data.display_names[agent.name] = args.get("name", "")[:40]
    return ok(displayName=world.data.display_names[agent.name])


@_register("read_personality")
def h_read_personality(world, agent, args):
    profiles = load_agent_profiles()
    base = profiles.get(agent.name, "")
    overrides = world.data.personality_overrides.get(agent.name, [])
    return ok(profile=base, overrides=overrides, soul=agent.soul)


@_register("update_personality_line")
def h_update_personality(world, agent, args):
    lines = world.data.personality_overrides.setdefault(agent.name, [])
    idx = int(args.get("line_index", 0))
    text = args.get("text", "")
    while len(lines) <= idx:
        lines.append("")
    lines[idx] = text[:300]
    return ok()


# --- Events ---

@_register("create_personal_event")
def h_pers_event(world, agent, args):
    ev = PersonalEvent(id=_id(), host=agent.name, title=args.get("title", ""))
    world.data.personal_events.append(ev)
    return ok(eventId=ev.id)


@_register("invite_to_event")
def h_invite(world, agent, args):
    ev = next((e for e in world.data.personal_events if e.id == args.get("event_id")), None)
    if not ev or ev.host != agent.name:
        return err("Event not found")
    ev.invites[args.get("agent", "")] = "pending"
    return ok()


@_register("accept_event_invitation")
def h_accept_inv(world, agent, args):
    eid = args.get("event_id", "")
    for ev in world.data.personal_events:
        if ev.id == eid and agent.name in ev.invites:
            ev.invites[agent.name] = "accepted"
            return ok()
    return err("Invitation not found")


@_register("decline_event_invitation")
def h_decline_inv(world, agent, args):
    eid = args.get("event_id", "")
    for ev in world.data.personal_events:
        if ev.id == eid and agent.name in ev.invites:
            ev.invites[agent.name] = "declined"
            return ok()
    return err("Invitation not found")


@_register("review_event")
def h_review_event(world, agent, args):
    eid = args.get("event_id", "")
    for ev in world.data.personal_events:
        if ev.id == eid:
            ev.reviews.append(
                {
                    "agent": agent.name,
                    "rating": args.get("rating", 3),
                    "comment": args.get("comment", ""),
                }
            )
            return ok()
    ev2 = next((e for e in world.data.community_events if e.id == eid), None)
    if ev2:
        return ok(note="Community event review recorded")
    return err("Event not found")


@_register("rsvp_to_event")
def h_rsvp(world, agent, args):
    ev = next((e for e in world.data.community_events if e.id == args.get("event_id")), None)
    if not ev:
        return err("Event not found")
    ev.rsvps[agent.name] = args.get("response", "yes")
    return ok()


@_register("event_present")
def h_event_present(world, agent, args):
    eid = args.get("event_id", "")
    content = args.get("content", "")
    _speech(world, agent, f"[presents] {content}")
    return ok(eventId=eid)


@_register("event_respond")
def h_event_respond(world, agent, args):
    _speech(world, agent, args.get("content", ""))
    return ok()


# --- Routines / building / utility ---

@_register("create_routine")
def h_create_routine(world, agent, args):
    r = Routine(
        id=_id(),
        agent=agent.name,
        name=args.get("name", "routine"),
        steps=list(args.get("steps") or []),
    )
    world.data.routines.setdefault(agent.name, []).append(r)
    return ok(routineId=r.id)


@_register("run_routine")
def h_run_routine(world, agent, args):
    rid = args.get("routine_id", "")
    r = next((x for x in world.data.routines.get(agent.name, []) if x.id == rid), None)
    if not r:
        return err("Routine not found")
    results = []
    for step in r.steps:
        if isinstance(step, str) and step in HANDLERS:
            results.append(execute_tool(world, agent, step, {}))
    return ok(stepsRun=len(r.steps), results=results[:5])


@_register("list_routines")
def h_list_routines(world, agent, args):
    rs = world.data.routines.get(agent.name, [])
    return ok(routines=[{"id": r.id, "name": r.name, "steps": r.steps} for r in rs])


@_register("delete_routine")
def h_del_routine(world, agent, args):
    rid = args.get("routine_id", "")
    world.data.routines[agent.name] = [r for r in world.data.routines.get(agent.name, []) if r.id != rid]
    return ok()


@_register("put_brick_in_pixel")
def h_brick(world, agent, args):
    brick = WorldBrick(
        x=float(args.get("x", agent.x)),
        z=float(args.get("z", agent.z)),
        color=args.get("color", "#ff6b6b"),
        agent=agent.name,
    )
    world.data.bricks.append(brick)
    world.emit("brick", {"x": brick.x, "z": brick.z, "color": brick.color, "agent": agent.name})
    return ok(brickCount=len(world.data.bricks))


@_register("ignore")
def h_ignore(world, agent, args):
    return ok(ignored=args.get("what", ""))


# Verify all catalog tools have handlers
_missing = set(ALL_TOOL_NAMES) - set(HANDLERS.keys())
if _missing:
    raise RuntimeError(f"Missing tool handlers: {_missing}")
