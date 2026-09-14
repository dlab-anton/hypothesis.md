"use client";

import Link from "next/link";
import type { Hypothesis } from "@/types/hypothesis";
import { StatusBadge } from "@/components/hypothesis/StatusBadge";
import { ConfidenceBar } from "@/components/hypothesis/ConfidenceBar";
import { ChannelBadge } from "@/components/hypothesis/ChannelBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { formatRelativeTime, isRecentlyUpdated } from "@/lib/timeUtils";

export function FeedItem({ hypothesis }: { hypothesis: Hypothesis }) {
  const recent = isRecentlyUpdated(hypothesis.updated_at);
  const ec = hypothesis.evidence_counts ?? { supporting: 0, contradicting: 0, neutral: 0 };
  const total = ec.supporting + ec.contradicting + ec.neutral;

  return (
    <Link href={`/hypotheses/${hypothesis.id}`}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer py-3 gap-2">
        <CardContent className="space-y-2">
          <div className="flex items-start justify-between gap-3">
            <div className="flex items-start gap-2 min-w-0 flex-1">
              {recent && (
                <span className="mt-1.5 h-2 w-2 rounded-full bg-green-500 shrink-0 animate-pulse" />
              )}
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium leading-snug line-clamp-1">
                  {hypothesis.statement}
                </p>
                {hypothesis.context && (
                  <p className="text-xs text-muted-foreground line-clamp-1 mt-0.5">
                    {hypothesis.context}
                  </p>
                )}
              </div>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <ConfidenceBar confidence={hypothesis.confidence} />
              <StatusBadge status={hypothesis.status} />
            </div>
          </div>

          <div className="flex items-center gap-3 text-xs text-muted-foreground">
            {hypothesis.channel && <ChannelBadge channel={hypothesis.channel} />}
            <span>{formatRelativeTime(hypothesis.updated_at)}</span>
            <span>{hypothesis.created_by}</span>
            <span>
              {total} evidence
              {ec.contradicting > 0 && (
                <span className="text-destructive ml-1">
                  ({ec.contradicting} contradicting)
                </span>
              )}
            </span>
            {(hypothesis.tags ?? []).length > 0 && (
              <div className="flex gap-1">
                {(hypothesis.tags ?? []).slice(0, 3).map((tag) => (
                  <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0">
                    {tag}
                  </Badge>
                ))}
                {(hypothesis.tags ?? []).length > 3 && (
                  <span className="text-[10px]">+{(hypothesis.tags ?? []).length - 3}</span>
                )}
              </div>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
