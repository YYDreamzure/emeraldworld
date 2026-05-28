import { useState } from "react";
import { useWorldSocket } from "./hooks/useWorldSocket";
import { WorldScene } from "./components/WorldScene";
import { Dashboard } from "./components/Dashboard";
import { ContentPanel } from "./components/ContentPanel";
import { ResizablePanels } from "./components/ResizablePanels";
import { MemoryGraphPanel, MemoryGraphModal } from "./components/MemoryGraphPanel";
import { AgentsPanel } from "./components/AgentsPanel";
import { ToolsPanel } from "./components/ToolsPanel";
import "./styles.css";

type View = "world" | "dashboard" | "content" | "agents" | "tools";

export default function App() {
  const { snapshot, connected, send } = useWorldSocket();
  const [view, setView] = useState<View>("world");
  const [brainAgent, setBrainAgent] = useState<string | null>(null);
  const [memoryModalAgent, setMemoryModalAgent] = useState<string | null>(null);

  if (!snapshot) {
    return (
      <div className="loading">
        <h1>EMERGENCE WORLD</h1>
        <p>{connected ? "Loading world…" : "Connecting to simulation…"}</p>
        <p className="hint">Start the server: python -m sim.server</p>
      </div>
    );
  }

  const modalAgent = snapshot.agents.find((a) => a.name === memoryModalAgent);

  const openMemoryFor = (name: string) => {
    setBrainAgent(name);
    setMemoryModalAgent(name);
  };

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-accent">EMERGENCE</span> WORLD
          <span className="locale-badge">🇸🇬 Singapore</span>
        </div>
        <nav className="view-tabs">
          <button
            type="button"
            className={view === "world" ? "tab active" : "tab"}
            onClick={() => setView("world")}
          >
            World
          </button>
          <button
            type="button"
            className={view === "dashboard" ? "tab active" : "tab"}
            onClick={() => setView("dashboard")}
          >
            Dashboard
          </button>
          <button
            type="button"
            className={view === "content" ? "tab active" : "tab"}
            onClick={() => setView("content")}
          >
            Blogs & News
          </button>
          <button
            type="button"
            className={view === "agents" ? "tab active" : "tab"}
            onClick={() => setView("agents")}
          >
            Agents
          </button>
          <button
            type="button"
            className={view === "tools" ? "tab active" : "tab"}
            onClick={() => setView("tools")}
          >
            Tools
          </button>
        </nav>
        <div className="status">
          <span className={`dot ${connected ? "on" : ""}`} />
          {snapshot.running ? "Sim running" : "Paused"}
          <span className="model">{snapshot.model}</span>
        </div>
        <div className="controls">
          {brainAgent && view === "world" && (
            <button
              type="button"
              className="btn-expand-graph"
              onClick={() => setMemoryModalAgent(brainAgent)}
            >
              🧠 {brainAgent} memory
            </button>
          )}
          <button type="button" onClick={() => send("start")}>
            ▶ Run
          </button>
          <button type="button" className="secondary" onClick={() => send("stop")}>
            ⏸ Stop
          </button>
          <button type="button" className="secondary" onClick={() => send("step")}>
            ⏭ Step
          </button>
          <button
            type="button"
            className="secondary"
            onClick={() => {
              fetch("/api/sim/new", { method: "POST" }).then(() =>
                window.location.reload(),
              );
            }}
          >
            New run
          </button>
        </div>
      </header>
      <main
        className={
          view === "world"
            ? "main main-resizable"
            : view === "agents"
              ? "main main-agents"
              : view === "tools"
                ? "main main-tools"
                : view === "content"
                  ? "main main-content"
                  : "main main-dashboard"
        }
      >
        {view === "content" ? (
          <ContentPanel snapshot={snapshot} />
        ) : view === "agents" ? (
          <AgentsPanel
            snapshot={snapshot}
            onOpenMemory={(name) => setMemoryModalAgent(name)}
          />
        ) : view === "tools" ? (
          <ToolsPanel snapshot={snapshot} />
        ) : view === "world" ? (
          <ResizablePanels
            direction="horizontal"
            storageKey="ew-layout-world-h-v2"
            className="world-layout"
            defaultSizes={[0.48, 0.26, 0.26]}
            panels={[
              {
                id: "map",
                title: "Map",
                minRatio: 0.22,
                content: (
                  <section className="viewport">
                    <WorldScene snapshot={snapshot} />
                    {snapshot.activeAgent && (
                      <div className="active-banner">
                        <span className="pulse" />
                        {snapshot.activeAgent} is thinking…
                      </div>
                    )}
                  </section>
                ),
              },
              {
                id: "log",
                title: "Activity log",
                minRatio: 0.14,
                content: (
                  <div className="sidebar-inner scroll">
                    <p className="tick">Tick {snapshot.tick}</p>
                    <ul className="log">
                      {[...snapshot.log].reverse().map((line, i) => (
                        <li key={`${snapshot.tick}-${i}`}>{line}</li>
                      ))}
                    </ul>
                  </div>
                ),
              },
              {
                id: "roster",
                title: "Citizens & memory",
                minRatio: 0.18,
                content: (
                  <div className="sidebar-inner roster-panel">
                    <p className="panel-hint">
                      Click a citizen to open their memory graph (full-screen).
                      Drag orange gutters to resize panels.
                    </p>
                    <ul className="roster">
                      {snapshot.agents.map((a) => (
                        <li key={a.name}>
                          <button
                            type="button"
                            className={`roster-btn ${brainAgent === a.name ? "selected" : ""} ${a.isActive ? "active" : ""}`}
                            onClick={() => openMemoryFor(a.name)}
                          >
                            <span
                              className="swatch"
                              style={{
                                background: a.alive === false ? "#444" : a.color,
                              }}
                            />
                            <div>
                              <strong>{a.name}</strong>
                              <small>
                                {a.locationName} · {a.mood}
                                {a.memoryBrain != null
                                  ? ` · 🧠 ${a.memoryBrain.nodeCount ?? 0}`
                                  : ""}
                                {(a.personalTools?.length ?? 0) > 0
                                  ? ` · 🔧 ${a.personalTools!.length}`
                                  : ""}
                              </small>
                            </div>
                          </button>
                        </li>
                      ))}
                    </ul>
                    {brainAgent && (
                      <MemoryGraphPanel
                        agent={
                          snapshot.agents.find((a) => a.name === brainAgent) ??
                          snapshot.agents[0]
                        }
                        compact
                        onOpenFull={() => setMemoryModalAgent(brainAgent)}
                      />
                    )}
                  </div>
                ),
              },
            ]}
          />
        ) : (
          <Dashboard
            snapshot={snapshot}
            onOpenMemory={(name) => setMemoryModalAgent(name)}
          />
        )}
      </main>
      {modalAgent && (
        <MemoryGraphModal
          agent={modalAgent}
          onClose={() => setMemoryModalAgent(null)}
        />
      )}
    </div>
  );
}
