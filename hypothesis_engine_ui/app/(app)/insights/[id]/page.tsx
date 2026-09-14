"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { getInsight } from "@/lib/apiClient";
import { ChannelBadge } from "@/components/hypothesis/ChannelBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/timeUtils";
import { JsonDisplay } from "@/components/hypothesis/JsonDisplay";
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
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let current = true;
    getInsight(id)
      .then((data) => {
        if (current) setInsight(data);
      })
      .catch((e) => {
        if (current) setError(e instanceof Error ? e.message : "Failed to load insight");
      });
    return () => {
      current = false;
    };
  }, [id, retry]);

  if (error) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
          <Link href="/board">&larr; Back to research</Link>
        </Button>
        <div
          className="flex flex-wrap items-center justify-between gap-4 border-y py-4 text-sm text-destructive"
          role="alert"
        >
          <div>
            <p className="font-medium">Failed to load insight</p>
            <p className="mt-1 text-xs opacity-80">{error}</p>
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setError(null);
              setRetry((value) => value + 1);
            }}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  if (!insight) {
    return (
      <div className="text-muted-foreground" role="status">
        Loading insight…
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
        <Link href="/board">&larr; Back to research</Link>
      </Button>
      <InsightContent insight={insight} />
    </div>
  );
}

export function InsightContent({ insight }: { insight: Insight }) {
  const typeColor = TYPE_COLOR[insight.insight_type] || "text-gray-600";
  return (
    <article className="space-y-6">
      <header className="space-y-4 border-b pb-6">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary" className={`text-xs px-2 py-0.5 ${typeColor}`}>
            {insight.insight_type}
          </Badge>
          <ChannelBadge channel={insight.channel} />
        </div>
        <p className="whitespace-pre-wrap break-words text-lg leading-relaxed">{insight.content}</p>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span>{insight.created_by}</span>
          <time dateTime={insight.updated_at}>
            Updated {formatRelativeTime(insight.updated_at)}
          </time>
          {insight.updated_by && <span>Updated by {insight.updated_by}</span>}
        </div>
      </header>
      {insight.metadata && Object.keys(insight.metadata).length > 0 ? (
        <section aria-labelledby="insight-metadata-heading">
          <h2 id="insight-metadata-heading" className="mb-3 text-sm font-semibold">
            Metadata
          </h2>
          <JsonDisplay data={insight.metadata} />
        </section>
      ) : null}
    </article>
  );
}
