"use client";

import { Progress } from "@/components/ui/progress";

export function ConfidenceBar({ confidence }: { confidence: number | null }) {
  if (confidence === null || confidence === undefined) {
    return <span className="text-xs text-muted-foreground">No confidence set</span>;
  }

  const pct = Math.round(confidence * 100);
  const indicatorColor =
    confidence >= 0.7
      ? "[&>[data-slot=progress-indicator]]:bg-green-500"
      : confidence >= 0.4
        ? "[&>[data-slot=progress-indicator]]:bg-amber-500"
        : "[&>[data-slot=progress-indicator]]:bg-red-500";

  return (
    <div className="flex items-center gap-2">
      <Progress value={pct} className={`h-2 w-20 ${indicatorColor}`} />
      <span className="text-xs font-mono text-muted-foreground">{pct}%</span>
    </div>
  );
}
