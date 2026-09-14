"use client";

import type { CalibrationBucket } from "@/types/hypothesis";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface Props {
  buckets: CalibrationBucket[];
}

export function CalibrationChart({ buckets }: Props) {
  const W = 280;
  const H = 160;
  const PAD_L = 36;
  const PAD_R = 12;
  const PAD_T = 8;
  const PAD_B = 24;
  const plotW = W - PAD_L - PAD_R;
  const plotH = H - PAD_T - PAD_B;

  const barW = plotW / buckets.length - 4;

  const yLabels = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <svg
      viewBox={`0 0 ${W} ${H}`}
      className="w-full h-auto overflow-visible"
      preserveAspectRatio="xMidYMid meet"
    >
      {/* Y-axis grid + labels */}
      {yLabels.map((v) => {
        const y = PAD_T + plotH - v * plotH;
        return (
          <g key={v}>
            <line
              x1={PAD_L} y1={y} x2={W - PAD_R} y2={y}
              stroke="currentColor" strokeOpacity={0.08} strokeWidth={1}
            />
            <text
              x={PAD_L - 6} y={y + 3}
              textAnchor="end" fontSize={8}
              fill="currentColor" fillOpacity={0.35}
            >
              {Math.round(v * 100)}%
            </text>
          </g>
        );
      })}

      {/* Perfect calibration diagonal */}
      <line
        x1={PAD_L}
        y1={PAD_T + plotH}
        x2={PAD_L + plotW}
        y2={PAD_T}
        stroke="currentColor"
        strokeOpacity={0.15}
        strokeWidth={1}
        strokeDasharray="4 3"
      />

      {/* Bars */}
      {buckets.map((b, i) => {
        const x = PAD_L + i * (plotW / buckets.length) + 2;
        const hitRate = b.hit_rate ?? 0;
        const barH = hitRate * plotH;
        const y = PAD_T + plotH - barH;

        // Color: green if close to diagonal, amber/red if far
        const error = Math.abs((b.midpoint ?? 0) - hitRate);
        const fill =
          b.count === 0
            ? "transparent"
            : error < 0.1
              ? "#22c55e"
              : error < 0.2
                ? "#eab308"
                : "#ef4444";

        return (
          <Tooltip key={i}>
            <TooltipTrigger asChild>
              <rect
                x={x}
                y={b.count === 0 ? PAD_T : y}
                width={barW}
                height={b.count === 0 ? plotH : Math.max(barH, 1)}
                fill={fill}
                fillOpacity={b.count === 0 ? 0 : 0.7}
                stroke={b.count === 0 ? "currentColor" : fill}
                strokeOpacity={b.count === 0 ? 0.15 : 0.9}
                strokeWidth={1}
                strokeDasharray={b.count === 0 ? "3 2" : "none"}
                rx={2}
                className="cursor-pointer"
              />
            </TooltipTrigger>
            <TooltipContent side="top" className="text-xs">
              <p className="font-medium">
                {Math.round((b.midpoint ?? 0) * 100)}% confidence bucket
              </p>
              <p className="text-muted-foreground">
                {b.count > 0
                  ? `Hit rate: ${Math.round(hitRate * 100)}% (n=${b.count})`
                  : "No predictions"}
              </p>
            </TooltipContent>
          </Tooltip>
        );
      })}

      {/* X-axis labels */}
      {buckets.map((b, i) => {
        const x = PAD_L + i * (plotW / buckets.length) + 2 + barW / 2;
        return (
          <text
            key={i}
            x={x}
            y={H - 4}
            textAnchor="middle"
            fontSize={8}
            fill="currentColor"
            fillOpacity={0.4}
          >
            {Math.round((b.midpoint ?? 0) * 100)}%
          </text>
        );
      })}
    </svg>
  );
}
