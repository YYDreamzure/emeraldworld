import type { WorldSnapshot } from "../types";

const METRIC_ORDER = ["M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8", "M9"];

export function AwiPanel({ snapshot }: { snapshot: WorldSnapshot }) {
  const awi = snapshot.awi;
  if (!awi?.metrics) {
    return (
      <section className="awi-panel">
        <h2>AWI Metrics</h2>
        <p className="empty">No metrics yet — complete a round with Run.</p>
      </section>
    );
  }

  return (
    <section className="awi-panel">
      <h2>
        AWI · Round {awi.round} · Tick {awi.tick}
      </h2>
      {snapshot.runId && (
        <p className="run-id">
          Run <code>{snapshot.runId}</code>
        </p>
      )}
      <div className="awi-grid">
        {METRIC_ORDER.map((id) => {
          const m = awi.metrics[id];
          if (!m) return null;
          const change = m.change as number | undefined;
          const above =
            m.breakEven != null && typeof m.value === "number"
              ? m.value >= m.breakEven
              : null;
          return (
            <div key={id} className="awi-card">
              <span className="awi-id">{id}</span>
              <strong className="awi-name">{m.name}</strong>
              <span className="awi-value">
                {m.value}
                {m.unit ? ` ${m.unit}` : ""}
              </span>
              {change !== undefined && (
                <span className={`awi-change ${change >= 0 ? "pos" : "neg"}`}>
                  {change >= 0 ? "+" : ""}
                  {change} vs start
                </span>
              )}
              {above !== null && m.breakEven != null && (
                <span className={`awi-breakeven ${above ? "pos" : "neg"}`}>
                  break-even {m.breakEven}: {above ? "✓" : "✗"}
                </span>
              )}
              {m.note && <p className="awi-note">{m.note}</p>}
            </div>
          );
        })}
      </div>
    </section>
  );
}
