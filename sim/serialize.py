import time

from sim.activity import DAY_NAMES, current_period, is_weekend
from sim.agents_meta import AGENT_META, PORTRAIT_BASE
from sim.config import OLLAMA_MODEL
from sim.governance import list_proposals_dict
from sim.landmarks import LANDMARK_BY_ID, LANDMARKS
from sim.awi import compute_awi
from sim.memory_graph import brain_graph_for_ui
from sim.personal_capabilities import all_personal_tools, capability_to_dict
from sim.vitality import energy_status, hours_at_zero, hours_until_death
from sim.world import WorldState


def world_snapshot(world: WorldState) -> dict:
    h = world.history
    ongoing = h.ongoing_events()
    recent = h.recent_events(30)
    now = time.time()
    live = world.live_agent_names()

    awi = compute_awi(world, h)

    return {
        "tick": world.tick,
        "round": world.round_count,
        "runId": world.run_id,
        "startedAt": world.started_at,
        "running": world.running,
        "activeAgent": world.active_agent,
        "model": OLLAMA_MODEL,
        "theme": "singapore",
        "population": {"alive": len(live), "total": len(world.agents)},
        "activity": {
            "simHour": world.data.sim_hour_of_day,
            "simDay": world.data.sim_day_number,
            "dayOfWeek": DAY_NAMES[world.data.sim_day_of_week % 7],
            "weekend": is_weekend(world.data.sim_day_of_week),
            "currentPeriod": world.data.current_activity_window,
            "label": current_period(world).label,
        },
        "awi": awi,
        "landmarks": [
            {
                "id": lm.id,
                "name": lm.name,
                "x": lm.x,
                "z": lm.z,
                "description": lm.description,
                "buildingType": lm.building_type,
            }
            for lm in LANDMARKS
        ],
        "agents": [
            {
                "name": a.name,
                "role": AGENT_META.get(a.name, {}).get("role", "Citizen"),
                "color": AGENT_META.get(a.name, {}).get("color", "#ffffff"),
                "portrait": f"{PORTRAIT_BASE}/{a.name}.png",
                "locationId": a.location_id,
                "locationName": world.location(a).name,
                "homeName": LANDMARK_BY_ID[a.home_id].name if a.home_id in LANDMARK_BY_ID else "",
                "x": a.x,
                "z": a.z,
                "mood": a.mood,
                "energy": a.energy,
                "knowledge": a.knowledge,
                "influence": a.influence,
                "credits": a.credits,
                "gesture": a.gesture,
                "displayName": world.data.display_names.get(a.name, a.name),
                "alive": a.alive,
                "energyStatus": energy_status(a),
                "hoursAtZero": hours_at_zero(a, now) if a.energy <= 0 and a.alive else 0,
                "hoursUntilDeath": hours_until_death(a, now),
                "deathCause": a.death_cause,
                "speech": a.speech,
                "emoticon": a.emoticon,
                "isActive": a.is_active,
                "jailed": a.jailed_until is not None and a.jailed_until > now,
                "communityServiceHours": a.community_service_hours,
                "courtCaseId": a.active_court_case_id,
                "restrained": a.disabled_until is not None and a.disabled_until > now,
                "restrainedBy": a.disabled_by,
                "personalTools": [
                    capability_to_dict(c)
                    for c in world.data.personal_capabilities.get(a.name, [])
                ],
                "activityWindow": a.activity_window,
                "health": a.health,
                "severelyIll": a.severely_ill,
                "memories": [m.text for m in a.memories[-5:]],
                "memoryBrain": brain_graph_for_ui(a),
                "thoughts": [
                    h.to_action_dict(t) for t in h.agent_thoughts(a.name, 40)
                ],
                "planLog": [
                    h.to_action_dict(t) for t in h.agent_plan_log(a.name, 30)
                ],
                "speechLog": [
                    h.to_action_dict(t) for t in h.agent_speech_log(a.name, 40)
                ],
                "toolLog": [
                    h.to_action_dict(t) for t in h.agent_tool_log(a.name, 50)
                ],
                "actionLog": [
                    h.to_action_dict(t) for t in h.agent_action_log(a.name, 40)
                ],
                "todos": a.todos,
                "stats": h.agent_stats(a.name),
            }
            for a in world.agents.values()
        ],
        "proposals": list_proposals_dict(world),
        "singaporeLawAmendments": [
            {
                "ruleNumber": a.rule_number,
                "crimeTypes": a.crime_types,
                "ruleText": a.rule_text[:200],
            }
            for a in world.data.singapore_law_amendments[-20:]
        ],
        "weather": world.data.weather,
        "blogs": [
            {"id": b.id, "title": b.title, "author": b.author, "content": b.content[:500]}
            for b in world.data.blogs
            if b.status == "published"
        ][-20:],
        "newspaper": world.data.newspaper_articles[-3:],
        "billboard": [
            {"id": p.id, "author": p.author, "content": p.content[:300]}
            for p in world.data.billboard[-15:]
        ],
        "bricks": [
            {"x": b.x, "z": b.z, "color": b.color, "agent": b.agent}
            for b in world.data.bricks[-200:]
        ],
        "burnedLocations": [
            lid for lid, until in world.data.burned_until.items() if until > now
        ],
        "log": world.public_log[-80:],
        "personalToolsIndex": all_personal_tools(world),
        "dashboard": {
            "summary": {
                "tick": world.tick,
                "running": world.running,
                "activeAgent": world.active_agent,
                "ongoingEventCount": len(ongoing),
                "totalActions": len(h.actions),
                "totalEvents": len(h.events),
                "aliveCount": len(live),
                "round": world.round_count,
                "runId": world.run_id,
            },
            "awi": awi,
            "ongoingEvents": [h.to_event_dict(e) for e in ongoing],
            "recentEvents": [h.to_event_dict(e) for e in recent],
            "agents": {
                name: {
                    "actions": [
                        h.to_action_dict(a) for a in h.agent_actions(name, 35)
                    ],
                    "events": [
                        h.to_event_dict(e) for e in h.agent_events(name, 20)
                    ],
                    "stats": h.agent_stats(name),
                }
                for name in world.agents
            },
        },
    }
