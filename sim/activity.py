"""Singapore sim calendar — 24h world; agents choose their own schedule."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sim.world import AgentState, WorldState

DAY_NAMES = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


@dataclass(frozen=True)
class DayPeriod:
    """Named part of day for prompts (not a turn gate)."""

    id: str
    label: str
    start_hour: int
    end_hour: int


PERIODS: tuple[DayPeriod, ...] = (
    DayPeriod("night", "Night", 0, 6),
    DayPeriod("morning", "Morning", 6, 12),
    DayPeriod("afternoon", "Afternoon", 12, 18),
    DayPeriod("evening", "Evening", 18, 24),
)

PERIOD_BY_ID = {p.id: p for p in PERIODS}


def period_for_hour(hour: float) -> DayPeriod:
    h = int(hour) % 24
    for p in PERIODS:
        if p.start_hour <= h < p.end_hour:
            return p
    return PERIODS[0]


def assign_preferred_period(agent_index: int) -> str:
    """Soft preference hint only — agents may act any time."""
    return PERIODS[agent_index % len(PERIODS)].id


def is_weekend(day_index: int) -> bool:
    return day_index in (5, 6)  # Saturday, Sunday


def advance_sim_clock(world: WorldState, hours: float = 2.0) -> None:
    prev_hour = world.data.sim_hour_of_day
    world.data.sim_hour_of_day = (world.data.sim_hour_of_day + hours) % 24.0
    if world.data.sim_hour_of_day < prev_hour:
        world.data.sim_day_number += 1
        world.data.sim_day_of_week = (world.data.sim_day_of_week + 1) % 7
    world.data.current_activity_window = period_for_hour(world.data.sim_hour_of_day).id


def current_period(world: WorldState) -> DayPeriod:
    pid = world.data.current_activity_window or "morning"
    return PERIOD_BY_ID.get(pid, PERIODS[1])


def agents_active_this_round(world: WorldState) -> list[str]:
    """24/7 — all living agents may take turns."""
    return world.live_agent_names()


def datetime_context(world: WorldState) -> str:
    day_name = DAY_NAMES[world.data.sim_day_of_week % 7]
    weekend = is_weekend(world.data.sim_day_of_week)
    period = current_period(world)
    h = int(world.data.sim_hour_of_day)
    m = int((world.data.sim_hour_of_day % 1) * 60)
    wk = "WEEKEND — agents often rest, socialise, or pursue personal goals" if weekend else "Weekday"
    return (
        f"Day {world.data.sim_day_number + 1}, {day_name} ({wk}), "
        f"{h:02d}:{m:02d} SGT, {period.label}. "
        f"The world runs 24 hours; you choose when to act — no shift lock-out."
    )


def window_summary(world: WorldState) -> str:
    return datetime_context(world)
