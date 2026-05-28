import { useMemo, useState } from "react";
import { AwiPanel } from "./AwiPanel";
import { MemoryGraphPanel } from "./MemoryGraphPanel";
import { ResizablePanels } from "./ResizablePanels";
import type { Agent, WorldEvent, WorldSnapshot } from "../types";

function formatTime(ts: number | null) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString();
}

function kindIcon(kind: string) {
  switch (kind) {
    case "turn":
      return "◎";
    case "conversation":
      return "💬";
    case "travel":
      return "→";
    case "death":
      return "💀";
    default:
      return "•";
  }
}

function actionIcon(kind: string, tool: string | null) {
  if (kind === "reaction") return "↳";
  if (kind === "conversation") return "💬";
  if (kind === "turn_start") return "▶";
  if (tool === "go_to_place") return "→";
  if (tool === "say_to_agent") return "💬";
  if (tool === "think_aloud") return "💭";
  if (tool === "show_emoticon") return "✨";
  return "⚙";
}

const EMPTY_DASH: WorldSnapshot["dashboard"] = {
  summary: {
    tick: 0,
    running: false,
    activeAgent: null,
    ongoingEventCount: 0,
    totalActions: 0,
    totalEvents: 0,
  },
  ongoingEvents: [],
  recentEvents: [],
  agents: {},
};

export function Dashboard({
  snapshot,
  onOpenMemory,
}: {
  snapshot: WorldSnapshot;
  onOpenMemory?: (agentName: string) => void;
}) {
  const dash = snapshot.dashboard ?? EMPTY_DASH;
  const [selected, setSelected] = useState<string>(
    snapshot.activeAgent ?? snapshot.agents[0]?.name ?? "Anchor",
  );

  const agent = snapshot.agents.find((a) => a.name === selected);
  const agentDash = dash.agents[selected];

  const involvesSelected = (e: WorldEvent) => e.agents.includes(selected);

  const ongoingEvents = useMemo(
    () => dash.ongoingEvents.filter(involvesSelected),
    [dash.ongoingEvents, selected],
  );

  const completedEvents = useMemo(
    () =>
      dash.recentEvents.filter(
        (e) => e.status === "completed" && involvesSelected(e),
      ),
    [dash.recentEvents, selected],
  );

  return (
    <div className="dashboard">
      <section className="dash-summary">
        <div className="stat-card">
          <span className="stat-label">Tick</span>
          <span className="stat-value">{dash.summary.tick}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Status</span>
          <span className="stat-value">
            {dash.summary.running ? "Running" : "Paused"}
          </span>
        </div>
        <div className="stat-card accent">
          <span className="stat-label">Ongoing</span>
          <span className="stat-value">{dash.summary.ongoingEventCount}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Actions</span>
          <span className="stat-value">{dash.summary.totalActions}</span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Alive</span>
          <span className="stat-value">
            {dash.summary.aliveCount ?? snapshot.population?.alive ?? "—"}
            /{snapshot.population?.total ?? 10}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Events</span>
          <span className="stat-value">{dash.summary.totalEvents}</span>
        </div>
        {dash.summary.activeAgent && (
          <div className="stat-card live">
            <span className="stat-label">Active</span>
            <span className="stat-value">{dash.summary.activeAgent}</span>
          </div>
        )}
      </section>

      <AwiPanel snapshot={snapshot} />

      <ResizablePanels
        direction="horizontal"
        storageKey="ew-layout-dashboard-h-v2"
        className="dash-grid"
        defaultSizes={[0.32, 0.18, 0.5]}
        panels={[
          {
            id: "events",
            title: "Events & proposals",
            minRatio: 0.2,
            content: (
        <section className="dash-panel events-panel">
          <h2>Ongoing events</h2>
          <p className="panel-hint">Involving {selected}</p>
          {ongoingEvents.length === 0 ? (
            <p className="empty">No active events for this citizen.</p>
          ) : (
            <ul className="event-list">
              {ongoingEvents.map((ev) => (
                <EventRow key={ev.id} ev={ev} />
              ))}
            </ul>
          )}

          <h2>Town Hall proposals</h2>
          {(snapshot.proposals?.length ?? 0) === 0 ? (
            <p className="empty">No removal proposals yet.</p>
          ) : (
            <ul className="proposal-list">
              {snapshot.proposals!.map((p) => (
                <li key={p.id} className={`proposal-card ${p.status}`}>
                  <strong>
                    Remove {p.targetAgent}
                  </strong>
                  <p>{p.reason}</p>
                  <small>
                    {p.status} · {p.votesFor}/{p.votesNeeded} for · by {p.proposer}
                  </small>
                </li>
              ))}
            </ul>
          )}

          <h2>Previous events</h2>
          <ul className="event-list scroll">
            {completedEvents.length === 0 ? (
              <li className="empty">No completed events for this citizen yet.</li>
            ) : (
              completedEvents.map((ev) => (
                <EventRow key={ev.id} ev={ev} completed />
              ))
            )}
          </ul>
        </section>
            ),
          },
          {
            id: "citizens",
            title: "Citizens",
            minRatio: 0.12,
            content: (
        <section className="dash-panel agents-panel">
          <h2>Citizens</h2>
          <ul className="agent-picker">
            {snapshot.agents.map((a) => (
              <li key={a.name}>
                <button
                  type="button"
                  className={`${selected === a.name ? "selected" : ""} ${a.alive === false ? "dead" : ""} ${a.energyStatus === "critical" ? "critical" : ""}`}
                  onClick={() => {
                    setSelected(a.name);
                    onOpenMemory?.(a.name);
                  }}
                >
                  <span className="swatch" style={{ background: a.alive === false ? "#444" : a.color }} />
                  <span className="picker-name">
                    {a.name}
                    {a.alive === false ? " †" : ` ${Math.round(a.energy)}%`}
                  </span>
                  {a.isActive && <span className="live-dot" />}
                </button>
              </li>
            ))}
          </ul>
        </section>
            ),
          },
          {
            id: "detail",
            title: "Agent detail",
            minRatio: 0.25,
            content: (
        <section className="dash-panel detail-panel">
          {agent && agentDash ? (
            <AgentDetail
              agent={agent}
              actions={agentDash.actions}
              events={agentDash.events ?? []}
              onOpenMemory={onOpenMemory}
            />
          ) : (
            <p className="empty">Select an agent</p>
          )}
        </section>
            ),
          },
        ]}
      />
    </div>
  );
}

function EventRow({ ev, completed }: { ev: WorldEvent; completed?: boolean }) {
  return (
    <li className={`event-card ${completed ? "completed" : "ongoing"}`}>
      <span className="event-kind">{kindIcon(ev.kind)}</span>
      <div>
        <strong>{ev.title}</strong>
        <p className="event-text">{ev.summary}</p>
        <small>
          Tick {ev.tick}
          {completed && ev.endedTick != null ? ` → ${ev.endedTick}` : ""} ·{" "}
          {formatTime(completed ? (ev.endedTs ?? ev.ts) : ev.ts)}
          {!completed ? ` · ${ev.agents.join(", ")}` : ""}
        </small>
      </div>
    </li>
  );
}

function AgentDetail({
  agent,
  actions,
  events,
  onOpenMemory,
}: {
  agent: Agent;
  actions: import("../types").ActionRecord[];
  events: WorldEvent[];
  onOpenMemory?: (agentName: string) => void;
}) {
  const completedAgentEvents = events.filter((e) => e.status === "completed");
  const ongoingAgentEvents = events.filter((e) => e.status === "ongoing");
  return (
    <>
      <header className="agent-header">
        <img
          src={agent.portrait}
          alt=""
          className="portrait"
          onError={(e) => {
            (e.target as HTMLImageElement).style.display = "none";
          }}
        />
        <div>
          <div className="agent-title-row">
            <h2>{agent.name}</h2>
            <button
              type="button"
              className="btn-expand-graph"
              onClick={() => onOpenMemory?.(agent.name)}
            >
              Open memory graph
            </button>
          </div>
          <p className="role">{agent.role}</p>
          <div className="agent-badges">
            {agent.alive === false && (
              <span className="badge dead">Deceased — {agent.deathCause}</span>
            )}
            {agent.isActive && <span className="badge live">Thinking</span>}
            {agent.energyStatus === "critical" && agent.alive !== false && (
              <span className="badge critical">Critical 0%</span>
            )}
            <span className="badge">{agent.mood}</span>
            <span className="badge">{agent.locationName}</span>
            {agent.homeName && <span className="badge">Home: {agent.homeName}</span>}
          </div>
        </div>
      </header>

      <div className="agent-metrics">
        <div>
          <span className="metric-label">Energy</span>
          <div className="bar">
            <div className="bar-fill" style={{ width: `${agent.energy}%` }} />
          </div>
          <span className="metric-val">{Math.round(agent.energy)}%</span>
        </div>
        <div className="metric-row">
          <span>{agent.credits ?? 0} CC</span>
          <span>{agent.stats.totalActions} actions</span>
          <span>{agent.stats.toolsUsed} tools</span>
        </div>
        {agent.alive !== false &&
          agent.energyStatus === "critical" &&
          agent.hoursUntilDeath != null && (
            <p className="death-warning">
              ☠ ~{agent.hoursUntilDeath.toFixed(1)}h until death if not recharged
            </p>
          )}
      </div>

      {agent.speech && (
        <div className="current-speech">
          {agent.emoticon && <span>{agent.emoticon}</span>}
          {agent.speech}
        </div>
      )}

      {agent.todos.length > 0 && (
        <div className="subsection">
          <h3>Todos</h3>
          <ul>
            {agent.todos.map((t, i) => (
              <li key={i}>{t}</li>
            ))}
          </ul>
        </div>
      )}

      {agent.memories.length > 0 && (
        <div className="subsection">
          <h3>Recent memories (long-term)</h3>
          <ul>
            {agent.memories.map((m, i) => (
              <li key={i}>{m}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="subsection memory-graph-section">
        <MemoryGraphPanel agent={agent} />
      </div>

      {(ongoingAgentEvents.length > 0 || completedAgentEvents.length > 0) && (
        <div className="subsection">
          <h3>Events & activity</h3>
          {ongoingAgentEvents.length > 0 && (
            <ul className="event-list compact">
              {ongoingAgentEvents.map((ev) => (
                <EventRow key={ev.id} ev={ev} />
              ))}
            </ul>
          )}
          {completedAgentEvents.length > 0 && (
            <ul className="event-list compact scroll">
              {completedAgentEvents.map((ev) => (
                <EventRow key={ev.id} ev={ev} completed />
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="subsection">
        <h3>Action history</h3>
        <ul className="action-timeline">
          {actions.length === 0 ? (
            <li className="empty">No actions recorded yet.</li>
          ) : (
            actions.map((a) => (
              <li key={a.id} className={a.ok ? "" : "failed"}>
                <span className="action-icon">{actionIcon(a.kind, a.tool)}</span>
                <div>
                  <p className="action-text">{a.detail || a.summary}</p>
                  <small>
                    Tick {a.tick} · {formatTime(a.ts)}
                    {a.location ? ` · ${a.location}` : ""}
                    {a.target ? ` → ${a.target}` : ""}
                  </small>
                </div>
              </li>
            ))
          )}
        </ul>
      </div>
    </>
  );
}
