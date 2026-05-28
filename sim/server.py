"""FastAPI server: WebSocket world stream + static game client."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from sim.runner import SimulationRunner
from sim.store import RunStore

ROOT = Path(__file__).resolve().parent.parent
CLIENT_DIST = ROOT / "client" / "dist"

runner = SimulationRunner()


class ConnectionManager:
    def __init__(self) -> None:
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket) -> None:
        await ws.accept()
        self.connections.append(ws)
        await ws.send_json({"type": "snapshot", "data": runner.snapshot()})

    def disconnect(self, ws: WebSocket) -> None:
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, snapshot: dict) -> None:
        dead: list[WebSocket] = []
        for ws in self.connections:
            try:
                await ws.send_json({"type": "snapshot", "data": snapshot})
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()
_loop: asyncio.AbstractEventLoop | None = None


def _schedule_broadcast(snapshot: dict) -> None:
    if _loop is None:
        return
    asyncio.run_coroutine_threadsafe(manager.broadcast(snapshot), _loop)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _loop
    _loop = asyncio.get_running_loop()
    runner.subscribe(_schedule_broadcast)
    yield
    runner.stop()


app = FastAPI(title="Emergence World Local", lifespan=lifespan)


@app.get("/api/state")
async def get_state():
    return runner.snapshot()


@app.get("/api/runs")
async def list_runs():
    return {"runs": RunStore.list_runs()}


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    data = RunStore.load_run(run_id)
    if not data:
        return {"error": "Run not found"}
    return data


@app.post("/api/sim/new")
async def new_simulation():
    if runner._task and not runner._task.done():
        runner._task.cancel()
    snap = runner.new_simulation()
    return {"ok": True, "runId": snap.get("runId"), "snapshot": snap}


@app.post("/api/sim/start")
async def start_sim():
    if runner.world.running and runner._task and not runner._task.done():
        return {"started": False, "running": True}
    if not runner.world.live_agent_names():
        return {"started": False, "error": "No living agents — start a new simulation"}
    runner.world.running = True
    runner._task = asyncio.create_task(runner._loop())
    return {"started": True, "running": True, "runId": runner.world.run_id}


@app.post("/api/sim/stop")
async def stop_sim():
    runner.stop()
    if runner._task:
        runner._task.cancel()
    return {"running": runner.world.running}


@app.post("/api/sim/step")
async def step_sim(agent: str | None = None):
    await runner.step_once(agent)
    return runner.snapshot()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await manager.connect(ws)
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("action") == "start":
                if not runner.world.running:
                    runner.world.running = True
                    runner._task = asyncio.create_task(runner._loop())
            elif msg.get("action") == "stop":
                runner.stop()
                if runner._task:
                    runner._task.cancel()
            elif msg.get("action") == "step":
                await runner.step_once(msg.get("agent"))
    except WebSocketDisconnect:
        manager.disconnect(ws)


if CLIENT_DIST.exists():
    app.mount("/assets", StaticFiles(directory=CLIENT_DIST / "assets"), name="assets")

    @app.get("/{full_path:path}")
    async def spa(full_path: str = ""):
        if full_path and (CLIENT_DIST / full_path).is_file():
            return FileResponse(CLIENT_DIST / full_path)
        return FileResponse(CLIENT_DIST / "index.html")
else:

    @app.get("/")
    async def no_client():
        return {
            "message": "Build the client: cd client && npm install && npm run build",
            "dev": "cd client && npm run dev  (proxies API to :8765)",
            "api": "/api/state",
            "websocket": "/ws",
        }


def main() -> None:
    import uvicorn

    uvicorn.run("sim.server:app", host="0.0.0.0", port=8765, reload=False)


if __name__ == "__main__":
    main()
