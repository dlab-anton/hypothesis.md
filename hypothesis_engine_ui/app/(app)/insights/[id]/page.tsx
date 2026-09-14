"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getInsight } from "@/lib/apiClient";
import { ChannelBadge } from "@/components/hypothesis/ChannelBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/timeUtils";
import type { Insight } from "@/types/hypothesis";

const TYPE_COLOR: Record<string, string> = {
  calibration: "text-sky-600",
  bias: "text-rose-600",
  prior: "text-amber-600",
  pattern: "text-violet-600",
};

export default function InsightDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const [insight, setInsight] = useState<Insight | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getInsight(id)
      .then(setInsight)
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load insight"));
  }, [id]);

  if (error) {
    return (
      <div className="space-y-4 max-w-2xl">
        <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
          <Link href="/board">&larr; Back to board</Link>
        </Button>
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          <p className="font-medium">Failed to load insight</p>
          <p className="mt-1 text-xs opacity-80">{error}</p>
        </div>
      </div>
    );
  }

  if (!insight) return <div className="text-muted-foreground">Loading...</div>;

  return (
    <div className="space-y-4 max-w-2xl">
      <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
        <Link href="/board">&larr; Back to board</Link>
      </Button>
      <InsightContent insight={insight} />
    </div>
  );
}

export function InsightContent({ insight }: { insight: Insight }) {
  const typeColor = TYPE_COLOR[insight.insight_type] || "text-gray-600";
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <Badge variant="secondary" className={`text-xs px-2 py-0.5 ${typeColor}`}>
          {insight.insight_type}
        </Badge>
        <ChannelBadge channel={insight.channel} />
      </div>
      <p className="text-sm leading-relaxed">{insight.content}</p>
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span>{insight.created_by}</span>
        <span>{formatRelativeTime(insight.created_at)}</span>
        {insight.updated_by && <span>Updated by {insight.updated_by}</span>}
      </div>
    </div>
  );
}
