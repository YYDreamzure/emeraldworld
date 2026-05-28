import { useMemo, useState } from "react";
import { createPortal } from "react-dom";
import type { Agent, MemoryBrain, MemoryBrainNode } from "../types";

interface LayoutNode extends MemoryBrainNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
}

function layoutGraph(
  nodes: MemoryBrainNode[],
  edges: { a: string; b: string; weight: number }[],
  width: number,
  height: number,
): LayoutNode[] {
  if (nodes.length === 0) return [];
  const cx = width / 2;
  const cy = height / 2;
  const radius = Math.min(width, height) * 0.38;
  const laid: LayoutNode[] = nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length;
    return {
      ...n,
      x: cx + radius * Math.cos(angle),
      y: cy + radius * Math.sin(angle),
      vx: 0,
      vy: 0,
    };
  });
  const byId = new Map(laid.map((n) => [n.id, n]));
  const linkStrength = (w: number) => 0.02 + (w / 100) * 0.06;

  for (let iter = 0; iter < 80; iter++) {
    for (let i = 0; i < laid.length; i++) {
      for (let j = i + 1; j < laid.length; j++) {
        const a = laid[i];
        const b = laid[j];
        let dx = b.x - a.x;
        let dy = b.y - a.y;
        const dist = Math.hypot(dx, dy) || 1;
        const repulse = 800 / (dist * dist);
        dx = (dx / dist) * repulse;
        dy = (dy / dist) * repulse;
        a.vx -= dx;
        a.vy -= dy;
        b.vx += dx;
        b.vy += dy;
      }
    }
    for (const e of edges) {
      const a = byId.get(e.a);
      const b = byId.get(e.b);
      if (!a || !b) continue;
      let dx = b.x - a.x;
      let dy = b.y - a.y;
      const dist = Math.hypot(dx, dy) || 1;
      const pull = linkStrength(e.weight) * (dist - 90);
      dx = (dx / dist) * pull;
      dy = (dy / dist) * pull;
      a.vx += dx;
      a.vy += dy;
      b.vx -= dx;
      b.vy -= dy;
    }
    for (const n of laid) {
      n.vx += (cx - n.x) * 0.002;
      n.vy += (cy - n.y) * 0.002;
      n.x += n.vx * 0.15;
      n.y += n.vy * 0.15;
      n.vx *= 0.85;
      n.vy *= 0.85;
      n.x = Math.max(24, Math.min(width - 24, n.x));
      n.y = Math.max(24, Math.min(height - 24, n.y));
    }
  }
  return laid;
}

function GraphSvg({
  nodes,
  edges,
  selectedId,
  onSelect,
  large = false,
}: {
  nodes: MemoryBrainNode[];
  edges: { a: string; b: string; weight: number }[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  large?: boolean;
}) {
  const w = large ? 640 : 480;
  const h = large ? 420 : 280;
  const laid = useMemo(
    () => layoutGraph(nodes, edges, w, h),
    [nodes, edges, w, h],
  );
  const byId = new Map(laid.map((n) => [n.id, n]));

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className={`memory-graph-svg ${large ? "large" : ""}`}
      role="img"
      aria-label="Agent memory graph"
    >
      {edges.map((e, i) => {
        const a = byId.get(e.a);
        const b = byId.get(e.b);
        if (!a || !b) return null;
        return (
          <line
            key={`${e.a}-${e.b}-${i}`}
            x1={a.x}
            y1={a.y}
            x2={b.x}
            y2={b.y}
            stroke="#4a4a5a"
            strokeWidth={Math.max(0.5, e.weight / 25)}
            opacity={0.75}
          />
        );
      })}
      {laid.map((n) => {
        const r = 6 + (n.strength / 100) * (large ? 14 : 10);
        const fill = n.protected ? "#4dd0e1" : "#ff8c00";
        return (
          <g
            key={n.id}
            className={`memory-node ${selectedId === n.id ? "selected" : ""}`}
            onClick={() => onSelect(selectedId === n.id ? null : n.id)}
            style={{ cursor: "pointer" }}
          >
            <circle cx={n.x} cy={n.y} r={r} fill={fill} opacity={0.9} />
            {n.reinforcementCount > 1 && (
              <text
                x={n.x}
                y={n.y + 3}
                textAnchor="middle"
                fontSize="9"
                fill="#111"
                fontWeight="700"
              >
                {n.reinforcementCount}
              </text>
            )}
          </g>
        );
      })}
    </svg>
  );
}

function useBrainData(agent: Agent, brain?: MemoryBrain) {
  const data = brain ?? agent.memoryBrain;
  const nodes = data?.nodes ?? data?.top ?? [];
  const edges = data?.edges ?? [];
  const nodeCount = data?.nodeCount ?? nodes.length;
  const isEmpty = !data || (nodeCount === 0 && nodes.length === 0);
  return { data, nodes, edges, nodeCount, isEmpty };
}

function MemoryGraphBody({
  agent,
  data,
  nodes,
  edges,
  compact,
  large,
}: {
  agent: Agent;
  data: MemoryBrain;
  nodes: MemoryBrainNode[];
  edges: { a: string; b: string; weight: number }[];
  compact?: boolean;
  large?: boolean;
}) {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = nodes.find((n) => n.id === selectedId);

  return (
    <>
      <div className="memory-graph-stats">
        <span>{data.nodeCount ?? nodes.length} nodes</span>
        <span>{data.edgeCount ?? 0} links</span>
        <span>{data.protectedCount ?? 0} protected</span>
      </div>
      <GraphSvg
        nodes={nodes}
        edges={edges}
        selectedId={selectedId}
        onSelect={setSelectedId}
        large={large}
      />
      <p className="memory-graph-legend">
        <span>
          <span className="legend-dot protected" /> Protected (soul / long-term)
        </span>
        <span>
          <span className="legend-dot episodic" /> Episodic (decays if unused)
        </span>
      </p>
      {selected && (
        <div className="memory-node-detail">
          <strong>{selected.protected ? "🔒 Protected" : "Episodic"}</strong>
          <p>{selected.text}</p>
          <small>
            Strength {selected.strength}
            {selected.reinforcementCount > 1
              ? ` · reinforced ×${selected.reinforcementCount}`
              : ""}
            {selected.source ? ` · ${selected.source}` : ""}
          </small>
        </div>
      )}
      {!compact && (
        <ul className="memory-node-list scroll">
          {nodes.map((n) => (
            <li key={n.id}>
              <button
                type="button"
                className={selectedId === n.id ? "selected" : ""}
                onClick={() => setSelectedId(n.id)}
              >
                {n.protected ? "🔒 " : ""}
                [{n.strength}] {n.text.slice(0, 120)}
                {n.text.length > 120 ? "…" : ""}
              </button>
            </li>
          ))}
        </ul>
      )}
      {nodes.length === 0 && (
        <p className="empty memory-graph-empty">
          {agent.name}&apos;s brain has no nodes yet — memories appear as agents act
          and use add_to_longterm_memory.
        </p>
      )}
    </>
  );
}

/** Full-screen overlay — portaled to document.body so it is never clipped. */
export function MemoryGraphModal({
  agent,
  onClose,
}: {
  agent: Agent;
  onClose: () => void;
}) {
  const { data, nodes, edges, isEmpty } = useBrainData(agent);

  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      className="memory-graph-modal"
      role="dialog"
      aria-modal="true"
      aria-labelledby="memory-graph-title"
      onClick={onClose}
    >
      <div
        className="memory-graph-modal-inner"
        onClick={(e) => e.stopPropagation()}
      >
        <header>
          <h2 id="memory-graph-title">Memory brain — {agent.name}</h2>
          <button type="button" className="btn-expand-graph" onClick={onClose}>
            Close
          </button>
        </header>
        {isEmpty || !data ? (
          <p className="empty memory-graph-empty">
            {agent.name}&apos;s memory brain is still forming. Run the simulation
            and store memories; the graph will populate on the next snapshot.
          </p>
        ) : (
          <MemoryGraphBody
            agent={agent}
            data={data}
            nodes={nodes}
            edges={edges}
            large
          />
        )}
      </div>
    </div>,
    document.body,
  );
}

export function MemoryGraphPanel({
  agent,
  brain,
  compact = false,
  defaultOpen = false,
  onOpenFull,
}: {
  agent: Agent;
  brain?: MemoryBrain;
  compact?: boolean;
  /** Open the portaled modal on mount */
  defaultOpen?: boolean;
  onOpenFull?: () => void;
}) {
  const [modalOpen, setModalOpen] = useState(defaultOpen);
  const { data, nodes, edges, isEmpty } = useBrainData(agent, brain);

  const openModal = () => {
    setModalOpen(true);
    onOpenFull?.();
  };

  if (isEmpty) {
    return (
      <div className="memory-graph-panel compact">
        <p className="empty memory-graph-empty">
          {agent.name}: no memory nodes yet.
        </p>
        <button type="button" className="btn-expand-graph" onClick={openModal}>
          Open memory view
        </button>
        {modalOpen && (
          <MemoryGraphModal agent={agent} onClose={() => setModalOpen(false)} />
        )}
      </div>
    );
  }

  return (
    <div className={`memory-graph-panel ${compact ? "compact" : ""}`}>
      <div className="memory-graph-header">
        <h3>Memory brain — {agent.name}</h3>
        <button type="button" className="btn-expand-graph" onClick={openModal}>
          Open full view
        </button>
      </div>
      <MemoryGraphBody
        agent={agent}
        data={data!}
        nodes={nodes}
        edges={edges}
        compact={compact}
      />
      {modalOpen && (
        <MemoryGraphModal agent={agent} onClose={() => setModalOpen(false)} />
      )}
    </div>
  );
}
