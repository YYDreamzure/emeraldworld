import {
  Fragment,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
  type PointerEvent as ReactPointerEvent,
} from "react";

export interface PanelSpec {
  id: string;
  title?: string;
  minRatio?: number;
  content: ReactNode;
}

interface ResizablePanelsProps {
  direction: "horizontal" | "vertical";
  storageKey: string;
  panels: PanelSpec[];
  className?: string;
  /** Default flex ratios when nothing stored (must match panel count) */
  defaultSizes?: number[];
}

function normalize(sizes: number[]): number[] {
  const sum = sizes.reduce((a, b) => a + b, 0);
  if (sum <= 0) return sizes.map(() => 1 / sizes.length);
  return sizes.map((n) => n / sum);
}

function loadSizes(
  key: string,
  count: number,
  mins: number[],
  defaults: number[],
): number[] {
  const fallback = normalize(
    defaults.length === count ? defaults : Array(count).fill(1 / count),
  );
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    const parsed = JSON.parse(raw) as number[];
    if (parsed.length !== count || parsed.some((n) => n <= 0 || !Number.isFinite(n))) {
      return fallback;
    }
    let sizes = normalize(parsed);
    sizes = sizes.map((s, i) => Math.max(s, mins[i] ?? 0.1));
    return normalize(sizes);
  } catch {
    return fallback;
  }
}

export function ResizablePanels({
  direction,
  storageKey,
  panels,
  className = "",
  defaultSizes,
}: ResizablePanelsProps) {
  const count = panels.length;
  const mins = panels.map((p) => p.minRatio ?? 0.1);
  const defaults =
    defaultSizes ??
    (count === 3 ? [0.48, 0.26, 0.26] : Array(count).fill(1 / count));

  const [sizes, setSizes] = useState<number[]>(() =>
    loadSizes(storageKey, count, mins, defaults),
  );
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    index: number;
    startPos: number;
    startSizes: number[];
  } | null>(null);

  useEffect(() => {
    setSizes((prev) => {
      if (prev.length === count) return prev;
      return loadSizes(storageKey, count, mins, defaults);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only reset when panel count changes
  }, [count, storageKey]);

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(sizes));
  }, [sizes, storageKey]);

  const onGutterDown = useCallback(
    (index: number, e: ReactPointerEvent) => {
      e.preventDefault();
      e.stopPropagation();
      dragRef.current = {
        index,
        startPos: direction === "horizontal" ? e.clientX : e.clientY,
        startSizes: [...sizes],
      };
      (e.target as HTMLElement).setPointerCapture(e.pointerId);
    },
    [direction, sizes],
  );

  const onGutterMove = useCallback(
    (e: ReactPointerEvent) => {
      const drag = dragRef.current;
      const el = containerRef.current;
      if (!drag || !el) return;
      const rect = el.getBoundingClientRect();
      const total =
        direction === "horizontal" ? rect.width : rect.height;
      if (total < 50) return;
      const pos = direction === "horizontal" ? e.clientX : e.clientY;
      const deltaRatio = (pos - drag.startPos) / total;
      const i = drag.index;
      const next = [...drag.startSizes];
      const min = mins[i] ?? 0.1;
      const minNext = mins[i + 1] ?? 0.1;
      let a = next[i] + deltaRatio;
      let b = next[i + 1] - deltaRatio;
      if (a < min) {
        b -= min - a;
        a = min;
      }
      if (b < minNext) {
        a -= minNext - b;
        b = minNext;
      }
      if (a < min || b < minNext) return;
      next[i] = a;
      next[i + 1] = b;
      setSizes(normalize(next));
    },
    [direction, mins],
  );

  const onGutterUp = useCallback((e: ReactPointerEvent) => {
    dragRef.current = null;
    try {
      (e.target as HTMLElement).releasePointerCapture(e.pointerId);
    } catch {
      /* ignore */
    }
  }, []);

  const isRow = direction === "horizontal";

  return (
    <div
      ref={containerRef}
      className={`resizable-panels ${isRow ? "resizable-row" : "resizable-col"} ${className}`}
    >
      {panels.map((panel, i) => (
        <Fragment key={panel.id}>
          <div
            className="resizable-panel-wrap"
            style={{ flex: `${sizes[i]} 1 160px` }}
            data-panel-id={panel.id}
          >
            {panel.title && (
              <div className="resizable-panel-title">{panel.title}</div>
            )}
            <div className="resizable-panel-body">{panel.content}</div>
          </div>
          {i < panels.length - 1 && (
            <div
              className={`resize-gutter ${isRow ? "gutter-v" : "gutter-h"}`}
              role="separator"
              aria-orientation={isRow ? "vertical" : "horizontal"}
              title="Drag to resize"
              onPointerDown={(e) => onGutterDown(i, e)}
              onPointerMove={onGutterMove}
              onPointerUp={onGutterUp}
              onPointerCancel={onGutterUp}
            />
          )}
        </Fragment>
      ))}
    </div>
  );
}
