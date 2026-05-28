"""Persist simulation runs to results/runs/<run_id>/."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sim.config import OLLAMA_MODEL, ROOT, SIM_TIME_SCALE
from sim.awi import compute_awi
from sim.world import WorldState

RUNS_DIR = ROOT / "results" / "runs"


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{uuid4().hex[:6]}"


class RunStore:
    def __init__(self, run_id: str) -> None:
        self.run_id = run_id
        self.path = RUNS_DIR / run_id
        self.path.mkdir(parents=True, exist_ok=True)
        self._actions_offset = 0

    @classmethod
    def list_runs(cls, limit: int = 50) -> list[dict]:
        if not RUNS_DIR.exists():
            return []
        runs = []
        for p in sorted(RUNS_DIR.iterdir(), reverse=True):
            if not p.is_dir():
                continue
            meta_path = p / "meta.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                meta = {"id": p.name}
            runs.append(meta)
            if len(runs) >= limit:
                break
        return runs

    @classmethod
    def load_run(cls, run_id: str) -> dict | None:
        path = RUNS_DIR / run_id
        final = path / "final.json"
        if final.exists():
            return json.loads(final.read_text(encoding="utf-8"))
        meta_path = path / "meta.json"
        if meta_path.exists():
            data = {"meta": json.loads(meta_path.read_text(encoding="utf-8"))}
            rounds_path = path / "rounds.jsonl"
            if rounds_path.exists():
                data["rounds"] = [
                    json.loads(line)
                    for line in rounds_path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                ]
            return data
        return None

    def write_meta(self, world: WorldState, *, status: str = "running") -> None:
        meta = {
            "id": self.run_id,
            "status": status,
            "startedAt": world.started_at,
            "endedAt": world.ended_at,
            "model": OLLAMA_MODEL,
            "simTimeScale": SIM_TIME_SCALE,
            "theme": "singapore",
            "startingPopulation": len(world.agents),
        }
        (self.path / "meta.json").write_text(
            json.dumps(meta, indent=2), encoding="utf-8"
        )

    def append_actions(self, world: WorldState) -> None:
        actions = world.history.actions[self._actions_offset :]
        if not actions:
            return
        path = self.path / "actions.jsonl"
        with path.open("a", encoding="utf-8") as f:
            for a in actions:
                f.write(json.dumps(world.history.to_action_dict(a)) + "\n")
        self._actions_offset = len(world.history.actions)

    def save_round(self, world: WorldState, snapshot: dict) -> dict:
        awi = compute_awi(world, world.history)
        self.append_actions(world)
        doc = {
            "round": world.round_count,
            "tick": world.tick,
            "timestamp": time.time(),
            "population": {
                "alive": len(world.live_agent_names()),
                "total": len(world.agents),
            },
            "awi": awi,
            "snapshot": {
                "logTail": world.public_log[-20:],
                "proposals": len(world.proposals),
            },
        }
        with (self.path / "rounds.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(doc) + "\n")
        (self.path / "awi_latest.json").write_text(
            json.dumps(awi, indent=2), encoding="utf-8"
        )
        return awi

    def finalize(self, world: WorldState, snapshot: dict, *, reason: str) -> None:
        world.ended_at = time.time()
        awi = compute_awi(world, world.history)
        self.append_actions(world)
        final = {
            "meta": {
                "id": self.run_id,
                "status": "completed",
                "reason": reason,
                "startedAt": world.started_at,
                "endedAt": world.ended_at,
                "rounds": world.round_count,
                "ticks": world.tick,
                "model": OLLAMA_MODEL,
            },
            "awi": awi,
            "snapshot": snapshot,
        }
        (self.path / "final.json").write_text(
            json.dumps(final, indent=2, default=str), encoding="utf-8"
        )
        self.write_meta(world, status="completed")
