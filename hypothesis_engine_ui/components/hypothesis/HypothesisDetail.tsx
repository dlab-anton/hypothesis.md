"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getHypothesis,
  listEvidence,
  getTimeline,
  getLineage,
} from "@/lib/apiClient";
import { StatusBadge } from "@/components/hypothesis/StatusBadge";
import { ConfidenceBar } from "@/components/hypothesis/ConfidenceBar";
import { ChannelBadge } from "@/components/hypothesis/ChannelBadge";
import { MethodologySection } from "@/components/hypothesis/MethodologySection";
import { JsonDisplay } from "@/components/hypothesis/JsonDisplay";
import { ConfidenceTimeline } from "@/components/hypothesis/ConfidenceTimeline";
import { OverdueBadge } from "@/components/hypothesis/OverdueBadge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { EVIDENCE_CONFIG, EVENT_TYPE_LABELS } from "@/lib/constants";
import { formatRelativeTime } from "@/lib/timeUtils";
import Link from "next/link";
import type {
  Hypothesis,
  Evidence,
  TimelineEvent,
  EvidenceType,
  LineageResponse,
} from "@/types/hypothesis";

interface Props {
  id: string;
  modal?: boolean;
}

export function HypothesisDetail({ id, modal }: Props) {
  const [hypothesis, setHypothesis] = useState<Hypothesis | null>(null);
  const [evidence, setEvidence] = useState<Evidence[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [lineage, setLineage] = useState<LineageResponse | null>(null);
  const [loadedTabs, setLoadedTabs] = useState<Set<string>>(new Set(["evidence"]));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabError, setTabError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const [h, ev] = await Promise.all([getHypothesis(id), listEvidence(id)]);
        setHypothesis(h);
        setEvidence(ev);
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load hypothesis");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [id]);

  const handleTabChange = useCallback(
    (value: string) => {
      setTabError(null);
      if (value === "timeline" && !loadedTabs.has("timeline")) {
        getTimeline(id)
          .then((data) => {
            setTimeline(data);
            setLoadedTabs((prev) => new Set(prev).add("timeline"));
          })
          .catch((e) => {
            setTabError(e instanceof Error ? e.message : "Failed to load timeline");
          });
      }
      if (value === "lineage" && !loadedTabs.has("lineage")) {
        getLineage(id)
          .then((data) => {
            setLineage(data);
            setLoadedTabs((prev) => new Set(prev).add("lineage"));
          })
          .catch((e) => {
            setTabError(e instanceof Error ? e.message : "Failed to load lineage");
          });
      }
    },
    [id, loadedTabs],
  );

  if (loading) return <div className="text-muted-foreground">Loading...</div>;
  if (error) {
    return (
      <div className="space-y-4 max-w-4xl">
        {!modal && (
          <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
            <Link href="/hypotheses">&larr; Back to hypotheses</Link>
          </Button>
        )}
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          <p className="font-medium">Failed to load hypothesis</p>
          <p className="mt-1 text-xs opacity-80">{error}</p>
        </div>
      </div>
    );
  }
  if (!hypothesis) return <div className="text-destructive">Hypothesis not found</div>;

  return (
    <div className="space-y-4 max-w-4xl">
      {!modal && (
        <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
          <Link href="/hypotheses">&larr; Back to hypotheses</Link>
        </Button>
      )}

      {/* Header */}
      <div className="space-y-2">
        <div className="flex items-start justify-between gap-4">
          <h1 className="text-xl font-bold leading-snug">{hypothesis.statement}</h1>
          <div className="flex items-center gap-2 flex-shrink-0">
            <OverdueBadge hypothesis={hypothesis} />
            <StatusBadge status={hypothesis.status} />
          </div>
        </div>
        {hypothesis.context && (
          <p className="text-sm text-muted-foreground">{hypothesis.context}</p>
        )}
        <div className="flex items-center gap-4">
          {hypothesis.channel && <ChannelBadge channel={hypothesis.channel} />}
          <ConfidenceBar confidence={hypothesis.confidence} />
          <span className="text-xs text-muted-foreground">by {hypothesis.created_by}</span>
          <span className="text-xs text-muted-foreground">
            {new Date(hypothesis.created_at).toLocaleDateString()}
          </span>
        </div>
        {(hypothesis.tags ?? []).length > 0 && (
          <div className="flex flex-wrap gap-1">
            {(hypothesis.tags ?? []).map((tag) => (
              <Badge key={tag} variant="secondary" className="text-xs">{tag}</Badge>
            ))}
          </div>
        )}
      </div>

      {/* Methodology */}
      <MethodologySection hypothesis={hypothesis} />

      {/* Evidence summary */}
      {hypothesis.evidence_counts && (
        <div className="flex gap-4 text-sm">
          <span className="text-green-600">{hypothesis.evidence_counts.supporting} supporting</span>
          <span className="text-red-600">{hypothesis.evidence_counts.contradicting} contradicting</span>
          <span className="text-muted-foreground">{hypothesis.evidence_counts.neutral} neutral</span>
        </div>
      )}

      {/* Confidence over time */}
      <ConfidenceTimeline evidence={evidence} />

      {/* Tab error */}
      {tabError && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          <p className="font-medium">Failed to load tab data</p>
          <p className="mt-1 text-xs opacity-80">{tabError}</p>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="evidence" onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="lineage">Lineage</TabsTrigger>
        </TabsList>

        <TabsContent value="evidence">
          <div className="space-y-2">
            {evidence.length === 0 ? (
              <p className="text-sm text-muted-foreground">No evidence yet.</p>
            ) : (
              evidence.map((ev) => {
                const config = EVIDENCE_CONFIG[ev.evidence_type as EvidenceType] || EVIDENCE_CONFIG.neutral;
                return (
                  <div key={ev.id} className={`border-l-4 ${config.border} pl-3 py-2`}>
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm">{ev.content}</p>
                      <Badge variant="outline" className={`text-xs ${config.color}`}>{config.label}</Badge>
                    </div>
                    <div className="flex gap-3 mt-1 text-xs text-muted-foreground">
                      {ev.source && <span>Source: {ev.source}</span>}
                      {ev.strength !== null && <span>Strength: {ev.strength}</span>}
                      {ev.confidence_after != null && (
                        <span className="font-mono">Conf: {Math.round(ev.confidence_after * 100)}%</span>
                      )}
                      <span>{ev.created_by}</span>
                      <span>{formatRelativeTime(ev.created_at)}</span>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </TabsContent>

        <TabsContent value="timeline">
          <div className="space-y-2">
            {timeline.length === 0 ? (
              <p className="text-sm text-muted-foreground">No events yet.</p>
            ) : (
              <div className="relative pl-4 border-l-2 border-muted space-y-4">
                {timeline.map((ev) => (
                  <div key={ev.id} className="relative">
                    <div className="absolute -left-[1.3rem] top-1 w-2.5 h-2.5 rounded-full bg-muted-foreground" />
                    <div className="text-sm font-medium">
                      {EVENT_TYPE_LABELS[ev.event_type] || ev.event_type}
                    </div>
                    {Object.keys(ev.data).length > 0 && (
                      <div className="mt-1">
                        <JsonDisplay data={ev.data as Record<string, unknown>} />
                      </div>
                    )}
                    <div className="text-xs text-muted-foreground mt-1">
                      {ev.created_by} &middot; {formatRelativeTime(ev.created_at)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="lineage">
          <div className="space-y-2">
            {!lineage || lineage.chain.length <= 1 ? (
              <p className="text-sm text-muted-foreground">No revision history.</p>
            ) : (
              <div className="space-y-2">
                {lineage.chain.map((h, i) => (
                  <div
                    key={h.id}
                    className={`p-3 rounded-md border ${
                      h.id === id ? "border-foreground bg-muted/50" : "border-muted"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-xs text-muted-foreground mr-2">v{i + 1}</span>
                        {h.id === id ? (
                          <span className="text-sm font-medium">{h.statement}</span>
                        ) : (
                          <Link href={`/hypotheses/${h.id}`} className="text-sm font-medium text-blue-600 hover:underline">
                            {h.statement}
                          </Link>
                        )}
                      </div>
                      <StatusBadge status={h.status} />
                    </div>
                    <div className="text-xs text-muted-foreground mt-1">
                      {h.created_by} &middot; {new Date(h.created_at).toLocaleDateString()}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
