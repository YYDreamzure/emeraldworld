import { Fragment, useState } from "react";
import { MemoryGraphPanel } from "./MemoryGraphPanel";
import { ResizablePanels } from "./ResizablePanels";
import type { ActionRecord, Agent, WorldSnapshot } from "../types";

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function MetaLine({ item }: { item: ActionRecord }) {
  return (
    <small>
      Tick {item.tick} · {formatTime(item.ts)}
      {item.location ? ` · ${item.location}` : ""}
    </small>
  );
}

function speechDirection(item: ActionRecord, viewer: string): string {
  if (item.kind === "conversation" && item.agent !== viewer) {
    return `From ${item.agent}`;
  }
  if (item.tool === "speak_to_all") {
    return "To everyone here";
  }
  if (item.target) {
    return `To ${item.target}`;
  }
  const to = item.args?.agent;
  if (typeof to === "string" && to) {
    return `To ${to}`;
  }
  return item.agent === viewer ? "Outgoing" : "";
}

function speechBody(item: ActionRecord): string {
  return (item.detail || item.summary).trim();
}

function toolPurpose(item: ActionRecord): string {
  const args = item.args ?? {};
  if (item.tool === "say_to_agent" && typeof args.message === "string") {
    return args.message;
  }
  if (item.tool === "think_aloud" && typeof args.thought === "string") {
    return args.thought;
  }
  if (item.tool === "go_to_place" && typeof args.place === "string") {
    return args.place;
  }
  if (typeof args.message === "string") {
    return args.message;
  }
  if (typeof args.reason === "string") {
    return args.reason;
  }
  if (typeof args.description === "string") {
    return args.description;
  }
  return (item.detail || item.summary).trim();
}

function thoughtText(item: ActionRecord): string {
  const full = item.fullText?.trim();
  if (full) {
    return full;
  }
  if (item.kind === "plan") {
    return (item.detail || item.summary || "").trim();
  }
  const fromArgs =
    item.tool === "think_aloud" && typeof item.args?.thought === "string"
      ? item.args.thought.trim()
      : "";
  let text = (fromArgs || item.detail || item.summary || "").trim();
  if (text.toLowerCase().startsWith("thought:")) {
    text = text.slice("thought:".length).trim();
  }
  return text;
}

function ThoughtRow({ item }: { item: ActionRecord }) {
  const isPlan = item.kind === "plan";
  const text = thoughtText(item);
  return (
    <li className={`feed-item thought-item ${isPlan ? "plan-item" : ""}`}>
      <span className="feed-icon">{isPlan ? "📋" : "💭"}</span>
      <div className="thought-body">
        {isPlan && (
          <p className="feed-plan-badge">
            Not executed — model wrote a plan instead of calling tools
          </p>
        )}
        <div className="feed-text thought-full">{text || "(empty)"}</div>
        <MetaLine item={item} />
      </div>
    </li>
  );
}

function SpeechRow({ item, viewer }: { item: ActionRecord; viewer: string }) {
  const dir = speechDirection(item, viewer);
  const incoming = item.kind === "conversation" && item.agent !== viewer;
  return (
    <li className={`feed-item speech-item ${incoming ? "incoming" : "outgoing"}`}>
      <span className="feed-icon">{incoming ? "👂" : "💬"}</span>
      <div>
        {dir && <p className="feed-direction">{dir}</p>}
        <p className="feed-text">{speechBody(item)}</p>
        <MetaLine item={item} />
        {item.tool && (
          <small className="feed-tool-tag">
            <code>{item.tool}</code>
          </small>
        )}
      </div>
    </li>
  );
}

function ActionRow({ item }: { item: ActionRecord }) {
  const text = (item.detail || item.summary).trim();
  return (
    <li className={`feed-item action-item ${item.ok ? "" : "failed"}`}>
      <span className="feed-icon">•</span>
      <div>
        <p className="feed-text">{text}</p>
        {(item.target || item.tool) && (
          <p className="feed-sub">
            {item.target && <span className="feed-target">→ {item.target}</span>}
            {item.target && item.tool && " · "}
            {item.tool && (
              <span>
                via <code>{item.tool}</code>
              </span>
            )}
          </p>
        )}
        <MetaLine item={item} />
      </div>
    </li>
  );
}

function ToolRow({ item }: { item: ActionRecord }) {
  const purpose = toolPurpose(item);
  const args = item.args ?? {};
  const argKeys = Object.keys(args).filter((k) => k !== "message" && k !== "thought");
  return (
    <li className={`feed-item tool-item ${item.ok ? "" : "failed"}`}>
      <span className="feed-icon">⚙</span>
      <div>
        <p className="feed-tool-name">
          <code>{item.tool}</code>
          {item.target && <span className="feed-target"> → {item.target}</span>}
        </p>
        {purpose && <p className="feed-text">{purpose}</p>}
        {argKeys.length > 0 && (
          <p className="feed-args">
            {argKeys.map((k) => (
              <span key={k}>
                <strong>{k}</strong>: {String(args[k]).slice(0, 120)}
              </span>
            ))}
          </p>
        )}
        <MetaLine item={item} />
      </div>
    </li>
  );
}

function FeedWindow({
  title,
  empty,
  items,
  render,
}: {
  title: string;
  empty: string;
  items: ActionRecord[];
  render: (item: ActionRecord) => React.ReactNode;
}) {
  return (
    <div className="agent-feed-window">
      <h3>{title}</h3>
      {items.length === 0 ? (
        <p className="empty">{empty}</p>
      ) : (
        <ul className="agent-feed-list scroll">
          {items.map((item) => (
            <Fragment key={item.id}>{render(item)}</Fragment>
          ))}
        </ul>
      )}
    </div>
  );
}

export function AgentsPanel({
  snapshot,
  onOpenMemory,
}: {
  snapshot: WorldSnapshot;
  onOpenMemory?: (name: string) => void;
}) {
  const [selected, setSelected] = useState(
    snapshot.activeAgent ?? snapshot.agents[0]?.name ?? "Anchor",
  );

  const agent: Agent | undefined = snapshot.agents.find(
    (a) => a.name === selected,
  );
  const thoughts = [
    ...(agent?.planLog ?? []),
    ...(agent?.thoughts ?? []),
  ].sort((a, b) => b.ts - a.ts);
  const speechLog = agent?.speechLog ?? [];
  const actionLog = agent?.actionLog ?? [];
  const toolLog = (agent?.toolLog ?? []).filter(
    (t) => t.tool !== "think_aloud" && t.kind !== "thought",
  );

  const feedGrid = agent ? (
    <ResizablePanels
      direction="vertical"
      storageKey={`ew-layout-agent-feeds-v2-${selected}`}
      defaultSizes={[0.5, 0.5]}
      className="agent-feeds-grid"
      panels={[
        {
          id: "top",
          minRatio: 0.2,
          content: (
            <ResizablePanels
              direction="horizontal"
              storageKey={`ew-layout-agent-feeds-top-${selected}`}
              defaultSizes={[0.5, 0.5]}
              panels={[
                {
                  id: "thoughts",
                  title: "Thoughts",
                  minRatio: 0.2,
                  content: (
                    <FeedWindow
                      title="Thoughts & plans"
                      empty="No thoughts or unexecuted plans yet."
                      items={thoughts}
                      render={(t) => <ThoughtRow item={t} />}
                    />
                  ),
                },
                {
                  id: "speech",
                  title: "Speech",
                  minRatio: 0.2,
                  content: (
                    <FeedWindow
                      title="Speech"
                      empty="No speech or messages yet."
                      items={speechLog}
                      render={(t) => (
                        <SpeechRow item={t} viewer={agent.name} />
                      )}
                    />
                  ),
                },
              ]}
            />
          ),
        },
        {
          id: "bottom",
          minRatio: 0.2,
          content: (
            <ResizablePanels
              direction="horizontal"
              storageKey={`ew-layout-agent-feeds-bottom-${selected}`}
              defaultSizes={[0.5, 0.5]}
              panels={[
                {
                  id: "actions",
                  title: "Actions",
                  minRatio: 0.2,
                  content: (
                    <FeedWindow
                      title="Actions"
                      empty="No world actions yet (travel, work, justice, etc.)."
                      items={actionLog}
                      render={(t) => <ActionRow item={t} />}
                    />
                  ),
                },
                {
                  id: "tools",
                  title: "Tools",
                  minRatio: 0.2,
                  content: (
                    <FeedWindow
                      title="Tools used"
                      empty="No tool calls recorded yet."
                      items={toolLog}
                      render={(t) => <ToolRow item={t} />}
                    />
                  ),
                },
              ]}
            />
          ),
        },
      ]}
    />
  ) : null;

  return (
    <div className="agents-tab">
      <ResizablePanels
        direction="horizontal"
        storageKey="ew-layout-agents-h-v2"
        className="agents-layout"
        defaultSizes={[0.2, 0.8]}
        panels={[
          {
            id: "picker",
            title: "Citizens",
            minRatio: 0.12,
            content: (
              <ul className="agent-picker-list">
                {snapshot.agents.map((a) => (
                  <li key={a.name}>
                    <button
                      type="button"
                      className={`roster-btn ${selected === a.name ? "selected" : ""} ${a.isActive ? "active" : ""}`}
                      onClick={() => setSelected(a.name)}
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
                          {a.role}
                          {a.memoryBrain
                            ? ` · 🧠 ${a.memoryBrain.nodeCount}`
                            : ""}
                        </small>
                      </div>
                      {a.isActive && <span className="live-dot" />}
                    </button>
                  </li>
                ))}
              </ul>
            ),
          },
          {
            id: "feeds",
            title: selected,
            minRatio: 0.5,
            content: agent ? (
              <div className="agent-feeds-column">
                <header className="agents-agent-header">
                  <div>
                    <h2>{agent.name}</h2>
                    <p className="role">{agent.role}</p>
                    <p className="panel-hint">
                      {agent.locationName} · {agent.mood} ·{" "}
                      {Math.round(agent.energy)}% energy
                    </p>
                  </div>
                  <button
                    type="button"
                    className="btn-expand-graph"
                    onClick={() => onOpenMemory?.(agent.name)}
                  >
                    Memory graph ({agent.memoryBrain?.nodeCount ?? 0} nodes)
                  </button>
                </header>
                {feedGrid}
                <details className="agents-memory-fold">
                  <summary>Memory graph preview</summary>
                  <MemoryGraphPanel agent={agent} compact />
                </details>
              </div>
            ) : (
              <p className="empty">Select a citizen</p>
            ),
          },
        ]}
      />
    </div>
  );
}
