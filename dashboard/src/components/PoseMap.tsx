import { useMemo } from "react";
import type { Place } from "../api";

interface Props {
  places: Place[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
}

const W = 300;
const H = 220;
const PAD = 26;

export default function PoseMap({ places, selectedId, onSelect }: Props) {
  const view = useMemo(() => {
    if (places.length === 0) return null;
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (const p of places) {
      minX = Math.min(minX, p.pose.x);
      maxX = Math.max(maxX, p.pose.x);
      minY = Math.min(minY, p.pose.y);
      maxY = Math.max(maxY, p.pose.y);
    }
    if (maxX - minX < 0.01) {
      minX -= 0.5;
      maxX += 0.5;
    }
    if (maxY - minY < 0.01) {
      minY -= 0.5;
      maxY += 0.5;
    }
    const sx = (x: number) => PAD + ((x - minX) / (maxX - minX)) * (W - PAD * 2);
    const sy = (y: number) =>
      H - PAD - ((y - minY) / (maxY - minY)) * (H - PAD * 2);
    return { minX, maxX, minY, maxY, sx, sy };
  }, [places]);

  if (!view) {
    return <div className="empty">No poses to plot yet.</div>;
  }

  return (
    <div className="map-wrap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Pose map">
        <text x={4} y={H - 6} fill="#93a3b8" fontSize="9">
          x {view.minX.toFixed(1)} to {view.maxX.toFixed(1)} m
        </text>
        <text x={4} y={12} fill="#93a3b8" fontSize="9">
          y {view.minY.toFixed(1)} to {view.maxY.toFixed(1)} m
        </text>
        {places.map((p) => {
          const cx = view.sx(p.pose.x);
          const cy = view.sy(p.pose.y);
          const selected = p.id === selectedId;
          const tick = 9;
          const tx = cx + Math.cos(p.pose.theta) * tick;
          const ty = cy - Math.sin(p.pose.theta) * tick;
          return (
            <g
              key={p.id}
              className="map-dot"
              onClick={() => onSelect(selected ? null : p.id)}
            >
              <title>{`${p.id} (${p.pose.x.toFixed(2)}, ${p.pose.y.toFixed(2)})`}</title>
              {selected && (
                <circle
                  cx={cx}
                  cy={cy}
                  r={9}
                  fill="none"
                  stroke="#34d399"
                  strokeWidth={1.5}
                />
              )}
              <circle
                cx={cx}
                cy={cy}
                r={5}
                fill={selected ? "#34d399" : "#60a5fa"}
                opacity={selected ? 1 : 0.75}
              />
              <line
                x1={cx}
                y1={cy}
                x2={tx}
                y2={ty}
                stroke={selected ? "#34d399" : "#93a3b8"}
                strokeWidth={1.5}
              />
            </g>
          );
        })}
      </svg>
    </div>
  );
}
