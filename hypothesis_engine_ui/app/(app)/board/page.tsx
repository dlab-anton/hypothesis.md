"use client";

import { useEffect, useState, useMemo } from "react";
import Link from "next/link";
import { Check, X, Minus, Lightbulb } from "lucide-react";
import type { Hypothesis, HypothesisStatus, Insight } from "@/types/hypothesis";
import { listHypotheses, listInsights } from "@/lib/apiClient";
import { STATUS_CONFIG } from "@/lib/constants";
import { useChannel } from "@/components/channel-provider";
import { ConfidenceBar } from "@/components/hypothesis/ConfidenceBar";
import { ChannelBadge } from "@/components/hypothesis/ChannelBadge";
import { OverdueBadge } from "@/components/hypothesis/OverdueBadge";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const IN_PROGRESS: HypothesisStatus[] = ["draft", "active", "testing"];
const CONCLUDED: HypothesisStatus[] = ["supported", "refuted", "inconclusive"];

const COLUMN_DOT: Record<string, string> = {
  draft: "bg-gray-400",
  active: "bg-blue-500",
  testing: "bg-amber-500",
};

const VERDICT_ICON: Record<string, { icon: typeof Check; color: string }> = {
  supported: { icon: Check, color: "text-green-600" },
  refuted: { icon: X, color: "text-red-600" },
  inconclusive: { icon: Minus, color: "text-orange-500" },
};

const INSIGHT_TYPE_COLOR: Record<string, string> = {
  calibration: "text-sky-600",
  bias: "text-rose-600",
  prior: "text-amber-600",
  pattern: "text-violet-600",
};

export default function BoardPage() {
  const [hypotheses, setHypotheses] = useState<Hypothesis[]>([]);
  const [insights, setInsights] = useState<Insight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { channel: channelFilter } = useChannel();
  const [agentFilter, setAgentFilter] = useState("all");

  useEffect(() => {
    listHypotheses({ limit: 200 })
      .then((res) => {
        const items = Array.isArray(res?.items) ? res.items : [];
        setHypotheses(items.filter((h) => h.status !== "revised"));
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });

    // Fetch insights independently — don't block the board if this fails
    listInsights({ limit: 50 })
      .then((res) => setInsights(Array.isArray(res) ? res : []))
      .catch(() => {}); // silently ignore — insights column stays empty
  }, []);

  // Extract unique agents from all loaded data
  const agents = useMemo(() => {
    const set = new Set<string>();
    hypotheses.forEach((h) => h.created_by && set.add(h.created_by));
    insights.forEach((i) => i.created_by && set.add(i.created_by));
    return [...set].sort();
  }, [hypotheses, insights]);

  // Apply filters
  const filteredHypotheses = useMemo(() => {
    return hypotheses.filter((h) => {
      if (channelFilter && h.channel !== channelFilter) return false;
      if (agentFilter !== "all" && h.created_by !== agentFilter) return false;
      return true;
    });
  }, [hypotheses, channelFilter, agentFilter]);

  const filteredInsights = useMemo(() => {
    return insights.filter((i) => {
      if (channelFilter && i.channel !== channelFilter) return false;
      if (agentFilter !== "all" && i.created_by !== agentFilter) return false;
      return true;
    });
  }, [insights, channelFilter, agentFilter]);

  const inProgressItems = IN_PROGRESS.reduce(
    (acc, status) => {
      acc[status] = filteredHypotheses.filter((h) => h.status === status && !h.is_archived);
      return acc;
    },
    {} as Record<string, Hypothesis[]>,
  );

  const concluded = filteredHypotheses.filter(
    (h) => CONCLUDED.includes(h.status) && !h.is_archived,
  );

  const archived = filteredHypotheses.filter((h) => h.is_archived);

  const activeCount = filteredHypotheses.filter((h) => !h.is_archived).length;

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64 text-muted-foreground">
        Loading board...
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-destructive">
        {error}
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <h1 className="text-xl font-bold">Board</h1>
          <Select value={agentFilter} onValueChange={setAgentFilter}>
            <SelectTrigger className="w-[150px] h-8 text-xs">
              <SelectValue placeholder="All agents" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All agents</SelectItem>
              {agents.map((ag) => (
                <SelectItem key={ag} value={ag}>{ag}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
        <span className="text-sm text-muted-foreground">
          {activeCount} active &middot; {archived.length} done
        </span>
      </div>

      <div className="flex-1 flex gap-3 overflow-x-auto pb-4">
        {/* In-progress columns */}
        {IN_PROGRESS.map((status) => (
          <BoardColumn key={status} status={status} items={inProgressItems[status] || []} />
        ))}

        {/* Concluded — single column with verdict icons */}
        <BoardShell
          dot={<span className="h-2.5 w-2.5 rounded-full bg-purple-500" />}
          label="Concluded"
          count={concluded.length}
          empty="No hypotheses"
        >
          {concluded.map((h) => (
            <KanbanCard key={h.id} hypothesis={h} showVerdict />
          ))}
        </BoardShell>

        {/* Insights */}
        <BoardShell
          dot={<Lightbulb className="h-3.5 w-3.5 text-amber-500" />}
          label="Insights"
          count={filteredInsights.length}
          empty="No insights yet"
        >
          {filteredInsights.map((ins) => (
            <InsightCard key={ins.id} insight={ins} />
          ))}
        </BoardShell>

        {/* Done */}
        <BoardShell
          dot={<span className="h-2.5 w-2.5 rounded-full bg-gray-400" />}
          label="Done"
          count={archived.length}
          empty="No archived hypotheses"
        >
          {archived.map((h) => (
            <KanbanCard key={h.id} hypothesis={h} showVerdict />
          ))}
        </BoardShell>
      </div>
    </div>
  );
}

function BoardShell({
  dot,
  label,
  count,
  empty,
  children,
}: {
  dot: React.ReactNode;
  label: string;
  count: number;
  empty: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex-shrink-0 w-64 flex flex-col rounded-xl border bg-muted/30">
      <div className="flex items-center justify-between px-3 py-2.5 border-b">
        <div className="flex items-center gap-2">
          {dot}
          <span className="text-sm font-medium">{label}</span>
        </div>
        <Badge variant="secondary" className="text-[10px] px-1.5 py-0 font-mono">
          {count}
        </Badge>
      </div>
      <div className="flex-1 overflow-y-auto p-2 flex flex-col gap-2">
        {count === 0 && (
          <p className="text-xs text-muted-foreground text-center py-6">{empty}</p>
        )}
        {children}
      </div>
    </div>
  );
}

function BoardColumn({ status, items }: { status: HypothesisStatus; items: Hypothesis[] }) {
  const config = STATUS_CONFIG[status];
  return (
    <BoardShell
      dot={<span className={`h-2.5 w-2.5 rounded-full ${COLUMN_DOT[status] || "bg-gray-400"}`} />}
      label={config.label}
      count={items.length}
      empty="No hypotheses"
    >
      {items.map((h) => (
        <KanbanCard key={h.id} hypothesis={h} />
      ))}
    </BoardShell>
  );
}

function KanbanCard({ hypothesis, showVerdict }: { hypothesis: Hypothesis; showVerdict?: boolean }) {
  const ec = hypothesis.evidence_counts ?? { supporting: 0, contradicting: 0, neutral: 0 };
  const total = ec.supporting + ec.contradicting + ec.neutral;
  const verdict = VERDICT_ICON[hypothesis.status];

  return (
    <Link href={`/hypotheses/${hypothesis.id}`}>
      <Card className="hover:shadow-sm transition-shadow cursor-pointer p-0">
        <CardContent className="p-3 space-y-2">
          <div className="flex items-start justify-between gap-1">
            <p className="text-xs font-medium leading-snug line-clamp-3">
              {hypothesis.statement}
            </p>
            {showVerdict && verdict ? (
              <verdict.icon className={`h-4 w-4 shrink-0 ${verdict.color}`} />
            ) : (
              <OverdueBadge hypothesis={hypothesis} />
            )}
          </div>

          <ConfidenceBar confidence={hypothesis.confidence} />

          <div className="flex items-center justify-between text-[11px] text-muted-foreground">
            <span>{total} evidence</span>
            <span>{hypothesis.created_by}</span>
          </div>

          <div className="flex flex-wrap items-center gap-1">
            {hypothesis.channel && (
              <ChannelBadge channel={hypothesis.channel} />
            )}
            {(hypothesis.tags ?? []).slice(0, 2).map((tag) => (
              <Badge
                key={tag}
                variant="secondary"
                className="text-[10px] px-1.5 py-0"
              >
                {tag}
              </Badge>
            ))}
            {(hypothesis.tags ?? []).length > 2 && (
              <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
                +{(hypothesis.tags ?? []).length - 2}
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}

function InsightCard({ insight }: { insight: Insight }) {
  const typeColor = INSIGHT_TYPE_COLOR[insight.insight_type] || "text-gray-600";
  return (
    <Link href={`/insights/${insight.id}`}>
      <Card className="p-0 hover:shadow-sm transition-shadow cursor-pointer">
        <CardContent className="p-3 space-y-1.5">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className={`text-[10px] px-1.5 py-0 ${typeColor}`}>
              {insight.insight_type}
            </Badge>
            <ChannelBadge channel={insight.channel} />
          </div>
          <p className="text-xs leading-snug line-clamp-4">
            {insight.content}
          </p>
          <div className="flex items-center justify-between text-[10px] text-muted-foreground">
            <span>{insight.created_by}</span>
            <span>{new Date(insight.created_at).toLocaleDateString()}</span>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
