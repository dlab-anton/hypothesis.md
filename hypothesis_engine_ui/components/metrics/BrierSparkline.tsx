"use client";

import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Props {
  scores: number[];
}

export function BrierSparkline({ scores }: Props) {
  if (scores.length < 2) return null;

  const W = 280;
  const H = 80;
  const PAD_L = 36;
  const PAD_R = 12;
  const PAD_T = 8;
  const PAD_B = 8;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  // Y range: 0 to max(0.5, max(scores))
  const yMax = Math.max(0.5, ...scores);
  const xStep = plotW / (scores.length - 1);

  const coords = scores.map((s, i) => ({
    x: PAD_L + i * xStep,
    y: PAD_T + plotH - (s / yMax) * plotH,
    score: s,
    index: i,
  }));

  const polyline = coords.map((c) => `${c.x},${c.y}`).join(" ");

  // Trend: compare first half to second half
  const mid = Math.floor(scores.length / 2);
  const firstHalf = scores.slice(0, mid);
  const secondHalf = scores.slice(mid);
  const firstAvg = firstHalf.reduce((a, b) => a + b, 0) / firstHalf.length;
  const secondAvg = secondHalf.reduce((a, b) => a + b, 0) / secondHalf.length;
  const trending = secondAvg < firstAvg - 0.01 ? "down" : secondAvg > firstAvg + 0.01 ? "up" : "flat";

  const strokeColor = trending === "down" ? "#22c55e" : trending === "up" ? "#ef4444" : "#9ca3af";

  // Reference lines
  const refs = [
    { value: 0.10, label: "excellent" },
    { value: 0.25, label: "coin flip" },
  ];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-auto overflow-visible"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Reference lines */}
      {refs
        .filter((r) => r.value <= yMax)
        .map((r) => {
          const y = PAD_T + plotH - (r.value / yMax) * plotH;
          return (
            <g key={r.label}>
              <line
                x1={PAD_L} y1={y} x2={W - PAD_R} y2={y}
                stroke="currentColor" strokeOpacity={0.1} strokeWidth={1}
                strokeDasharray="3 2"
              />
              <text
                x={PAD_L - 4} y={y + 3}
                textAnchor="end" fontSize={7}
                fill="currentColor" fillOpacity={0.3}
              >
                {r.value}
              </text>
            </g>
          );
        })}

      {/* Line */}
      <polyline
        points={polyline}
        fill="none"
        stroke={strokeColor}
        strokeOpacity={0.7}
        strokeWidth={1.5}
      />

      {/* Dots (only first, last, and every 5th for clarity) */}
      {coords
        .filter((_, i) => i === 0 || i === coords.length - 1 || i % 5 === 0)
        .map((c) => (
          <Tooltip key={c.index}>
            <TooltipTrigger asChild>
              <circle
                cx={c.x} cy={c.y} r={3}
                fill={strokeColor}
                stroke="white" strokeWidth={1}
                className="cursor-pointer"
              />
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              <p>Window {c.index + 1}: {c.score.toFixed(4)}</p>
            </TooltipContent>
          </Tooltip>
        ))}
    </svg>
  );
}
