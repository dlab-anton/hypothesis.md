"use client";

import { useEffect, useRef, useState, useCallback } from "react";
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
  const [loadingTabs, setLoadingTabs] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tabError, setTabError] = useState<string | null>(null);
  const [loadingMoreEvidence, setLoadingMoreEvidence] = useState(false);
  const [evidenceLoadError, setEvidenceLoadError] = useState<string | null>(null);
  const evidenceRequestId = useRef(0);
  const evidenceLoadPending = useRef(false);

  useEffect(() => {
    const requestId = ++evidenceRequestId.current;
    evidenceLoadPending.current = false;
    async function load() {
      try {
        const [h, ev] = await Promise.all([getHypothesis(id), listEvidence(id)]);
        if (requestId !== evidenceRequestId.current) return;
        setHypothesis(h);
        setEvidence(ev);
      } catch (e) {
        if (requestId !== evidenceRequestId.current) return;
        setError(e instanceof Error ? e.message : "Failed to load hypothesis");
      } finally {
        if (requestId === evidenceRequestId.current) setLoading(false);
      }
    }
    load();
  }, [id]);

  const loadMoreEvidence = useCallback(async () => {
    if (evidenceLoadPending.current) return;

    evidenceLoadPending.current = true;
    const requestId = ++evidenceRequestId.current;
    const offset = evidence.length;
    setLoadingMoreEvidence(true);
    setEvidenceLoadError(null);

    try {
      const nextPage = await listEvidence(id, undefined, offset);
      if (requestId !== evidenceRequestId.current) return;
      setEvidence((current) => {
        const existingIds = new Set(current.map((item) => item.id));
        return [...current, ...nextPage.filter((item) => !existingIds.has(item.id))];
      });
    } catch (e) {
      if (requestId === evidenceRequestId.current) {
        setEvidenceLoadError(e instanceof Error ? e.message : "Failed to load more evidence");
      }
    } finally {
      if (requestId === evidenceRequestId.current) {
        evidenceLoadPending.current = false;
        setLoadingMoreEvidence(false);
      }
    }
  }, [evidence.length, id]);

  const handleTabChange = useCallback(
    (value: string) => {
      setTabError(null);
      if (value === "timeline" && !loadedTabs.has("timeline")) {
        setLoadingTabs((prev) => new Set(prev).add("timeline"));
        getTimeline(id)
          .then((data) => {
            setTimeline(data);
            setLoadedTabs((prev) => new Set(prev).add("timeline"));
          })
          .catch((e) => {
            setTabError(e instanceof Error ? e.message : "Failed to load timeline");
          })
          .finally(() => {
            setLoadingTabs((prev) => {
              const next = new Set(prev);
              next.delete("timeline");
              return next;
            });
          });
      }
      if (value === "lineage" && !loadedTabs.has("lineage")) {
        setLoadingTabs((prev) => new Set(prev).add("lineage"));
        getLineage(id)
          .then((data) => {
            setLineage(data);
            setLoadedTabs((prev) => new Set(prev).add("lineage"));
          })
          .catch((e) => {
            setTabError(e instanceof Error ? e.message : "Failed to load lineage");
          })
          .finally(() => {
            setLoadingTabs((prev) => {
              const next = new Set(prev);
              next.delete("lineage");
              return next;
            });
          });
      }
    },
    [id, loadedTabs],
  );

  if (loading) return <div className="text-muted-foreground">Loading...</div>;
  if (error) {
    return (
      <div className="mx-auto max-w-3xl space-y-4">
        {!modal && (
          <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
            <Link href="/board">&larr; Back to research</Link>
          </Button>
        )}
        <div className="border-y py-4 text-sm text-destructive">
          <p className="font-medium">Failed to load hypothesis</p>
          <p className="mt-1 text-xs opacity-80">{error}</p>
        </div>
      </div>
    );
  }
  if (!hypothesis) return <div className="text-destructive">Hypothesis not found</div>;
  const totalEvidence = hypothesis.evidence_counts
    ? hypothesis.evidence_counts.supporting +
      hypothesis.evidence_counts.contradicting +
      hypothesis.evidence_counts.neutral
    : evidence.length;

  return (
    <div className="mx-auto max-w-3xl space-y-7">
      {!modal && (
        <Button variant="link" asChild className="p-0 h-auto text-muted-foreground">
          <Link href="/board">&larr; Back to research</Link>
        </Button>
      )}

      {/* Header */}
      <div className="space-y-3 border-b pb-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="min-w-0 flex-1 whitespace-pre-wrap break-words text-xl font-semibold leading-snug">
            {hypothesis.statement}
          </h1>
          <div className="flex shrink-0 flex-wrap items-center gap-2">
            <OverdueBadge hypothesis={hypothesis} />
            <StatusBadge status={hypothesis.status} />
          </div>
        </div>
        {hypothesis.context && (
          <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-muted-foreground">{hypothesis.context}</p>
        )}
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
          {hypothesis.channel && <ChannelBadge channel={hypothesis.channel} />}
          <ConfidenceBar confidence={hypothesis.confidence} />
          <span className="text-xs text-muted-foreground">by {hypothesis.created_by}</span>
          <span className="text-xs text-muted-foreground">
            Created {formatRelativeTime(hypothesis.created_at)}
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
        <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
          <span className="text-green-600">{hypothesis.evidence_counts.supporting} supporting</span>
          <span className="text-red-600">{hypothesis.evidence_counts.contradicting} contradicting</span>
          <span className="text-muted-foreground">{hypothesis.evidence_counts.neutral} neutral</span>
        </div>
      )}

      {/* Confidence over time */}
      <ConfidenceTimeline evidence={evidence} />

      {/* Tab error */}
      {tabError && (
        <div className="border-y py-4 text-sm text-destructive">
          <p className="font-medium">Failed to load tab data</p>
          <p className="mt-1 text-xs opacity-80">{tabError}</p>
        </div>
      )}

      {/* Tabs */}
      <Tabs defaultValue="evidence" onValueChange={handleTabChange}>
        <TabsList className="h-auto rounded-none border-b bg-transparent p-0">
          <TabsTrigger value="evidence">Evidence</TabsTrigger>
          <TabsTrigger value="timeline">Timeline</TabsTrigger>
          <TabsTrigger value="lineage">Lineage</TabsTrigger>
        </TabsList>

        <TabsContent value="evidence">
          <div className="divide-y">
            {totalEvidence > evidence.length ? (
              <p className="py-3 text-xs text-muted-foreground">
                Showing {evidence.length} of {totalEvidence} evidence records.
              </p>
            ) : null}
            {evidence.length === 0 ? (
              <p className="text-sm text-muted-foreground">No evidence yet.</p>
            ) : (
              evidence.map((ev) => {
                const config = EVIDENCE_CONFIG[ev.evidence_type as EvidenceType] || EVIDENCE_CONFIG.neutral;
                return (
                  <div key={ev.id} className="py-4">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <p className="min-w-0 flex-1 whitespace-pre-wrap break-words text-sm leading-relaxed">{ev.content}</p>
                      <Badge variant="outline" className={`text-xs ${config.color}`}>{config.label}</Badge>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                      {ev.source && <span className="break-all">Source: {ev.source}</span>}
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
            {evidenceLoadError ? (
              <div className="flex flex-wrap items-center justify-between gap-3 py-4 text-sm text-destructive" role="alert">
                <span>{evidenceLoadError}</span>
                <Button size="sm" variant="outline" onClick={() => void loadMoreEvidence()}>
                  Retry
                </Button>
              </div>
            ) : null}
            {evidence.length < totalEvidence && !evidenceLoadError ? (
              <div className="py-4">
                <Button
                  size="sm"
                  variant="outline"
                  disabled={loadingMoreEvidence}
                  onClick={() => void loadMoreEvidence()}
                >
                  {loadingMoreEvidence ? "Loading…" : "Load more evidence"}
                </Button>
              </div>
            ) : null}
          </div>
        </TabsContent>

        <TabsContent value="timeline">
          <div className="space-y-2">
            {loadingTabs.has("timeline") ? (
              <p className="text-sm text-muted-foreground" role="status">Loading timeline…</p>
            ) : timeline.length === 0 ? (
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
            {loadingTabs.has("lineage") ? (
              <p className="text-sm text-muted-foreground" role="status">Loading lineage…</p>
            ) : !lineage || lineage.chain.length <= 1 ? (
              <p className="text-sm text-muted-foreground">No revision history.</p>
            ) : (
              <div className="divide-y">
                {lineage.chain.map((h, i) => (
                  <div
                    key={h.id}
                    className={`py-3 ${h.id === id ? "font-medium" : ""}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <span className="text-xs text-muted-foreground mr-2">v{i + 1}</span>
                        {h.id === id ? (
                          <span className="text-sm font-medium">{h.statement}</span>
                        ) : (
                          <Link href={`/hypotheses/${h.id}`} className="break-words text-sm font-medium underline-offset-4 hover:underline">
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
