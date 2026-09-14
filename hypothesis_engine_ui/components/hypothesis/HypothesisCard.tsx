"use client";

import Link from "next/link";
import type { Hypothesis } from "@/types/hypothesis";
import { StatusBadge } from "./StatusBadge";
import { ConfidenceBar } from "./ConfidenceBar";
import { ChannelBadge } from "./ChannelBadge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { OverdueBadge } from "./OverdueBadge";

export function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const ec = hypothesis.evidence_counts ?? { supporting: 0, contradicting: 0, neutral: 0 };
  const total = ec.supporting + ec.contradicting + ec.neutral;

  return (
    <Link href={`/hypotheses/${hypothesis.id}`}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardHeader className="pb-2">
          <div className="flex items-start justify-between gap-2">
            <p className="text-sm font-medium leading-snug line-clamp-2">
              {hypothesis.statement}
            </p>
            <div className="flex items-center gap-1.5 flex-shrink-0">
              <OverdueBadge hypothesis={hypothesis} />
              <StatusBadge status={hypothesis.status} />
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-2">
          <ConfidenceBar confidence={hypothesis.confidence} />
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <div className="flex items-center gap-2">
              {hypothesis.channel && <ChannelBadge channel={hypothesis.channel} />}
              <span>{total} evidence</span>
            </div>
            <span>{hypothesis.created_by}</span>
          </div>
          {(hypothesis.tags ?? []).length > 0 && (
            <div className="flex flex-wrap gap-1">
              {(hypothesis.tags ?? []).slice(0, 4).map((tag) => (
                <Badge key={tag} variant="secondary" className="text-[10px] px-1.5 py-0">
                  {tag}
                </Badge>
              ))}
              {(hypothesis.tags ?? []).length > 4 && (
                <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                  +{(hypothesis.tags ?? []).length - 4}
                </Badge>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </Link>
  );
}
