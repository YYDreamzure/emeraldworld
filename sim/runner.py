import asyncio
import threading
from typing import Callable

from sim.config import AGENT_NAMES, SIM_HOURS_PER_ROUND
from sim.activity import advance_sim_clock, agents_active_this_round, window_summary
from sim.awi import compute_awi
from sim.serialize import world_snapshot
from sim.economy import maybe_end_pitch_cycle
from sim.turn import refresh_weather, run_agent_turn
from sim.world import WorldState


class SimulationRunner:
    def __init__(self) -> None:
        self.world = WorldState.bootstrap()
        self._task: asyncio.Task | None = None
        self._lock = threading.Lock()
        self._listeners: list[Callable[[dict], None]] = []

    def subscribe(self, listener: Callable[[dict], None]) -> None:
        self._listeners.append(listener)

    def _notify(self, snapshot: dict) -> None:
        for listener in list(self._listeners):
            listener(snapshot)

    def snapshot(self) -> dict:
        with self._lock:
            return world_snapshot(self.world)

    def new_simulation(self) -> dict:
        with self._lock:
            if self.world.running:
                self._finalize_run("restarted")
            self.world = WorldState.bootstrap()
            self.world.history.attach(self.world)
        snap = self.snapshot()
        self._notify(snap)
        return snap

    def _finalize_run(self, reason: str) -> None:
        store = self.world.store
        if store:
            snap = world_snapshot(self.world)
            store.finalize(self.world, snap, reason=reason)
        self.world.running = False

    def _complete_round(self) -> None:
        self.world.round_count += 1
        snap = world_snapshot(self.world)
        if self.world.store:
            awi = self.world.store.save_round(self.world, snap)
            snap["awi"] = awi
        else:
            snap["awi"] = compute_awi(self.world, self.world.history)
        self._notify(snap)

    def stop(self) -> None:
        with self._lock:
            self._finalize_run("stopped")
            if self._task and not self._task.done():
                self._task.cancel()

    async def _loop(self) -> None:
        self._notify(self.snapshot())
        while self.world.running:
            if not self.world.live_agent_names():
                with self._lock:
                    self.world.log("All agents deceased — simulation halted")
                    self._finalize_run("all_deceased")
                break

            with self._lock:
                advance_sim_clock(self.world, SIM_HOURS_PER_ROUND)
                active_names = agents_active_this_round(self.world)
                self.world.log(f"🕐 {window_summary(self.world)}")

            turns_this_round = 0
            for name in AGENT_NAMES:
                if not self.world.running:
                    break
                with self._lock:
                    if not self.world.agents[name].alive:
                        continue
                    if name not in active_names:
                        continue
                try:
                    await asyncio.to_thread(self._run_turn_sync, name)
                except Exception as e:
                    # Never crash the whole simulation loop on a single agent's LLM error.
                    with self._lock:
                        self.world.log(f"⚠ Turn failed for {name}: {type(e).__name__}: {e}")
                        # Ensure UI isn't stuck showing a dead/active agent.
                        self.world.set_active(None)
                        self._notify(self.snapshot())
                turns_this_round += 1
                await self._drain_boost_queue()

            with self._lock:
                maybe_end_pitch_cycle(self.world)
                if self.world.round_count % 12 == 0:
                    refresh_weather(self.world)
                self._maybe_publish_newspaper()
                if turns_this_round > 0:
                    self._complete_round()
                if not self.world.live_agent_names():
                    self.world.log("All agents deceased — simulation halted")
                    self._finalize_run("all_deceased")
                    break

            await asyncio.sleep(2)

        with self._lock:
            self._notify(self.snapshot())

    def _run_turn_sync(self, name: str, turn_kind: str = "regular") -> None:
        agent = self.world.agents[name]
        if not agent.alive:
            return

        def on_update(snap: dict) -> None:
            self._notify(snap)

        run_agent_turn(self.world, agent, on_update=on_update, turn_kind=turn_kind)

    async def _drain_boost_queue(self) -> None:
        while True:
            with self._lock:
                if not self.world.boost_queue or not self.world.running:
                    return
                name = self.world.boost_queue.pop(0)
                if not self.world.agents[name].alive:
                    continue
            await asyncio.to_thread(self._run_turn_sync, name, turn_kind="boost")

    def _maybe_publish_newspaper(self) -> None:
        """Daily-style digest from recent blogs (Reporter agent proxy)."""
        recent = [b for b in self.world.data.blogs if b.status == "published"][-5:]
        if not recent:
            return
        headline = recent[-1].title
        if self.world.data.newspaper_articles and self.world.data.newspaper_articles[-1].get("headline") == headline:
            return
        import time

        self.world.data.newspaper_articles.append(
            {
                "headline": headline,
                "articles": [{"title": b.title, "author": b.author} for b in recent],
                "ts": time.time(),
                "reporter": "Reporter",
            }
        )
        self.world.log(f"📰 Newspaper: {headline}")

    async def step_once(self, agent_name: str | None = None) -> None:
        with self._lock:
            if agent_name:
                name = agent_name
            else:
                live = self.world.live_agent_names()
                if not live:
                    return
                name = live[self.world.tick % len(live)]
            if not self.world.agents[name].alive:
                return
        await asyncio.to_thread(self._run_turn_sync, name)
