"use client";

import type { Evidence } from "@/types/hypothesis";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { formatRelativeTime } from "@/lib/timeUtils";

const EVIDENCE_COLORS: Record<string, string> = {
  supporting: "#22c55e",
  contradicting: "#ef4444",
  neutral: "#9ca3af",
};

interface Props {
  evidence: Evidence[];
}

export function ConfidenceTimeline({ evidence }: Props) {
  // Evidence comes newest-first from the API, reverse for chronological
  const chronological = [...evidence].reverse();

  const points = chronological
    .filter((ev) => ev.confidence_after !== null)
    .map((ev) => ({
      confidence: ev.confidence_after as number,
      time: ev.created_at,
      label: ev.content.length > 60 ? ev.content.slice(0, 57) + "..." : ev.content,
      color: EVIDENCE_COLORS[ev.evidence_type] || EVIDENCE_COLORS.neutral,
      type: ev.evidence_type,
    }));

  // Need at least 2 points for a meaningful chart
  if (points.length < 2) return null;

  const W = 500;
  const H = 120;
  const PAD_X = 32;
  const PAD_TOP = 12;
  const PAD_BOTTOM = 8;
  const plotW = W - PAD_X * 2;
  const plotH = H - PAD_TOP - PAD_BOTTOM;

  // X: evenly spaced, Y: confidence 0-1
  const xStep = plotW / (points.length - 1);
  const coords = points.map((p, i) => ({
    x: PAD_X + i * xStep,
    y: PAD_TOP + plotH - p.confidence * plotH,
    ...p,
  }));

  const polyline = coords.map((c) => `${c.x},${c.y}`).join(" ");

  const yLabels = [0, 0.25, 0.5, 0.75, 1.0];

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between">
        <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          Confidence over time
        </h3>
        <div className="flex items-center gap-3 text-[10px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-green-500" /> supporting
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-red-500" /> contradicting
          </span>
          <span className="flex items-center gap-1">
            <span className="inline-block w-2 h-2 rounded-full bg-gray-400" /> neutral
          </span>
        </div>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto overflow-visible" preserveAspectRatio="xMidYMid meet">
        {/* Grid lines */}
        {yLabels.map((v) => {
          const y = PAD_TOP + plotH - v * plotH;
          return (
            <g key={v}>
              <line
                x1={PAD_X} y1={y} x2={W - PAD_X} y2={y}
                stroke="currentColor" strokeOpacity={0.08} strokeWidth={1}
              />
              <text
                x={PAD_X - 6} y={y + 3}
                textAnchor="end" fontSize={9}
                fill="currentColor" fillOpacity={0.35}
              >
                {Math.round(v * 100)}%
              </text>
            </g>
          );
        })}

        {/* Line */}
        <polyline
          points={polyline}
          fill="none"
          stroke="currentColor"
          strokeOpacity={0.25}
          strokeWidth={1.5}
        />

        {/* Dots */}
        {coords.map((c, i) => (
          <Tooltip key={i}>
            <TooltipTrigger asChild>
              <circle
                cx={c.x} cy={c.y} r={4.5}
                fill={c.color}
                stroke="white" strokeWidth={1.5}
                className="cursor-pointer"
              />
            </TooltipTrigger>
            <TooltipContent side="top" className="max-w-xs">
              <p className="font-medium text-xs">{Math.round(c.confidence * 100)}%</p>
              <p className="text-xs text-muted-foreground">{c.label}</p>
              <p className="text-[10px] text-muted-foreground">{formatRelativeTime(c.time)}</p>
            </TooltipContent>
          </Tooltip>
        ))}
      </svg>
    </div>
  );
}
