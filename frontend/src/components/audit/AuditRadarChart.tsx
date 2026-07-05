// =============================================================================
// FGA CRM - Audit : Radar Chart SVG (8 axes) + helpers de geometrie
// (extrait de AuditResultPanel.tsx)
// =============================================================================

import type { RadarAxis } from './auditUtils';

export function RadarChart({ axes, size = 240 }: { axes: RadarAxis[]; size?: number }) {
  const cx = size / 2;
  const cy = size / 2;
  const radius = size / 2 - 30;
  const levels = 5; // Cercles concentriques (echelle 0-10, pas de 2)
  const n = axes.length;
  if (n < 3) return null;

  const angleStep = (2 * Math.PI) / n;
  // Depart en haut (-PI/2)
  const startAngle = -Math.PI / 2;

  const getPoint = (axisIndex: number, value: number, max: number = 10) => {
    const angle = startAngle + axisIndex * angleStep;
    const r = (value / max) * radius;
    return {
      x: cx + r * Math.cos(angle),
      y: cy + r * Math.sin(angle),
    };
  };

  // Grille concentrique
  const gridLines = Array.from({ length: levels }, (_, i) => {
    const levelRadius = ((i + 1) / levels) * radius;
    const points = Array.from({ length: n }, (_, j) => {
      const angle = startAngle + j * angleStep;
      return `${cx + levelRadius * Math.cos(angle)},${cy + levelRadius * Math.sin(angle)}`;
    });
    return points.join(' ');
  });

  // Axes (lignes du centre vers les bords)
  const axisLines = Array.from({ length: n }, (_, i) => {
    const angle = startAngle + i * angleStep;
    return {
      x2: cx + radius * Math.cos(angle),
      y2: cy + radius * Math.sin(angle),
    };
  });

  // Polygone des valeurs
  const dataPoints = axes.map((a, i) => getPoint(i, a.value));
  const dataPolygon = dataPoints.map((p) => `${p.x},${p.y}`).join(' ');

  // Labels
  const labelPositions = axes.map((a, i) => {
    const angle = startAngle + i * angleStep;
    const labelR = radius + 20;
    return {
      x: cx + labelR * Math.cos(angle),
      y: cy + labelR * Math.sin(angle),
      label: a.label_fr,
      value: a.value,
    };
  });

  return (
    <svg viewBox={`0 0 ${size} ${size}`} className="w-full max-w-[280px] mx-auto">
      {/* Grille */}
      {gridLines.map((points, i) => (
        <polygon
          key={i}
          points={points}
          fill="none"
          stroke="#e2e8f0"
          strokeWidth={i === levels - 1 ? 1.5 : 0.8}
        />
      ))}

      {/* Axes */}
      {axisLines.map((line, i) => (
        <line key={i} x1={cx} y1={cy} x2={line.x2} y2={line.y2} stroke="#cbd5e1" strokeWidth={0.5} />
      ))}

      {/* Polygone des valeurs */}
      <polygon
        points={dataPolygon}
        fill="rgba(99, 102, 241, 0.15)"
        stroke="#6366f1"
        strokeWidth={2}
      />

      {/* Points */}
      {dataPoints.map((p, i) => (
        <circle key={i} cx={p.x} cy={p.y} r={3} fill="#6366f1" />
      ))}

      {/* Labels */}
      {labelPositions.map((lp, i) => (
        <text
          key={i}
          x={lp.x}
          y={lp.y}
          textAnchor="middle"
          dominantBaseline="middle"
          className="text-[8px] fill-slate-500"
        >
          {lp.label}
        </text>
      ))}
    </svg>
  );
}
