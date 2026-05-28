import { useMemo, useState } from "react";
import { ResizablePanels } from "./ResizablePanels";
import type { Agent, PersonalTool, WorldSnapshot } from "../types";

function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleString();
}

function ToolCard({ tool, agentColor }: { tool: PersonalTool; agentColor?: string }) {
  return (
    <article className="personal-tool-card">
      <header className="tool-card-header">
        <div>
          <h3>{tool.name}</h3>
          <code className="tool-id">{tool.toolId}</code>
        </div>
        <span
          className="tool-owner-badge"
          style={agentColor ? { borderColor: agentColor, color: agentColor } : undefined}
        >
          {tool.owner}
        </span>
      </header>
      <p className="tool-effect-type">
        <span className="badge">{tool.effectLabel || tool.effectType}</span>
        <span className="private-tag">Private — only {tool.owner} can use</span>
      </p>
      <section className="tool-section">
        <h4>Purpose</h4>
        <p>{tool.purpose}</p>
        {tool.systemEffect && tool.systemEffect !== tool.purpose && (
          <p className="tool-system-effect">
            <small>System behaviour: {tool.systemEffect}</small>
          </p>
        )}
      </section>
      <section className="tool-section highlight">
        <h4>Why it was developed</h4>
        <p>{tool.whyDeveloped}</p>
      </section>
      <footer className="tool-meta">
        <span>Used {tool.timesUsed}×</span>
        <span>Learn −{tool.learnEnergyCost}% energy</span>
        <span>Use −{tool.useEnergyCost}% / call</span>
        {tool.durationHours > 0 && (
          <span>Effect ~{tool.durationHours}h sim</span>
        )}
        <span>Learned {formatTime(tool.learnedAt)}</span>
      </footer>
    </article>
  );
}

export function ToolsPanel({ snapshot }: { snapshot: WorldSnapshot }) {
  const [ownerFilter, setOwnerFilter] = useState<string>("all");

  const colorByAgent = useMemo(() => {
    const m: Record<string, string> = {};
    for (const a of snapshot.agents) {
      m[a.name] = a.color;
    }
    return m;
  }, [snapshot.agents]);

  const allTools = useMemo(() => {
    const fromIndex = snapshot.personalToolsIndex ?? [];
    if (fromIndex.length > 0) return fromIndex;
    return snapshot.agents.flatMap((a) => a.personalTools ?? []);
  }, [snapshot]);

  const filtered = useMemo(() => {
    if (ownerFilter === "all") return allTools;
    return allTools.filter((t) => t.owner === ownerFilter);
  }, [allTools, ownerFilter]);

  const countsByAgent = useMemo(() => {
    const c: Record<string, number> = {};
    for (const t of allTools) {
      c[t.owner] = (c[t.owner] ?? 0) + 1;
    }
    return c;
  }, [allTools]);

  const selectedAgent: Agent | undefined = snapshot.agents.find(
    (a) => a.name === ownerFilter,
  );

  return (
    <div className="tools-tab">
      <header className="tools-tab-header">
        <div>
          <h1>Personal tools</h1>
          <p className="panel-hint">
            Skills each agent invented with learn_personal_capability. They are
            not in the global tool registry — only the owner can invoke their
            cap_* tools.
          </p>
        </div>
        <div className="tools-summary">
          <span className="stat-pill">{allTools.length} tools total</span>
          <span className="stat-pill">
            {Object.keys(countsByAgent).length} agents with tools
          </span>
        </div>
      </header>
      <ResizablePanels
        direction="horizontal"
        storageKey="ew-layout-tools-h-v1"
        className="tools-layout"
        defaultSizes={[0.22, 0.78]}
        panels={[
          {
            id: "filter",
            title: "Filter by agent",
            minRatio: 0.14,
            content: (
              <ul className="agent-picker-list">
                <li>
                  <button
                    type="button"
                    className={`roster-btn ${ownerFilter === "all" ? "selected" : ""}`}
                    onClick={() => setOwnerFilter("all")}
                  >
                    <strong>All agents</strong>
                    <small>{allTools.length} tools</small>
                  </button>
                </li>
                {snapshot.agents.map((a) => (
                  <li key={a.name}>
                    <button
                      type="button"
                      className={`roster-btn ${ownerFilter === a.name ? "selected" : ""}`}
                      onClick={() => setOwnerFilter(a.name)}
                    >
                      <span className="swatch" style={{ background: a.color }} />
                      <div>
                        <strong>{a.name}</strong>
                        <small>{countsByAgent[a.name] ?? 0} personal tools</small>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            ),
          },
          {
            id: "tools",
            title: ownerFilter === "all" ? "All personal tools" : `${ownerFilter}'s tools`,
            minRatio: 0.4,
            content: (
              <div className="tools-list-wrap scroll">
                {filtered.length === 0 ? (
                  <p className="empty">
                    {ownerFilter === "all"
                      ? "No personal tools invented yet. Agents learn them at one-north TechHub with learn_personal_capability (costs energy)."
                      : `${ownerFilter} has not invented a personal tool yet.`}
                    {selectedAgent && (
                      <>
                        {" "}
                        Try running the sim — Brenda, for example, may learn
                        Emergency Restraint for urgent threats.
                      </>
                    )}
                  </p>
                ) : (
                  <div className="personal-tools-grid">
                    {filtered.map((tool) => (
                      <ToolCard
                        key={`${tool.owner}-${tool.id}`}
                        tool={tool}
                        agentColor={colorByAgent[tool.owner]}
                      />
                    ))}
                  </div>
                )}
              </div>
            ),
          },
        ]}
      />
    </div>
  );
}
