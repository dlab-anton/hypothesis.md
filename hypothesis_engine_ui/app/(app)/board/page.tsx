"use client";

import { useDeferredValue, useEffect, useLayoutEffect, useRef, useState } from "react";
import type { Hypothesis, Insight, InsightType, PaginatedResponse } from "@/types/hypothesis";
import { listHypotheses, listInsights } from "@/lib/apiClient";
import { useChannel } from "@/components/channel-provider";
import { ResearchRow } from "@/components/research-row";
import { Button } from "@/components/ui/button";
import {
  hypothesisListParams,
  pageRange,
  type ResearchStatusFilter,
} from "@/lib/research-filter";

const HYPOTHESIS_PAGE_SIZE = 40;
const INSIGHT_PAGE_SIZE = 12;

const STATUS_OPTIONS: Array<{ value: ResearchStatusFilter; label: string }> = [
  { value: "all", label: "All statuses" },
  { value: "draft", label: "Draft" },
  { value: "active", label: "Active" },
  { value: "testing", label: "Testing" },
  { value: "supported", label: "Supported" },
  { value: "refuted", label: "Refuted" },
  { value: "inconclusive", label: "Inconclusive" },
  { value: "revised", label: "Revised" },
  { value: "archived", label: "Archived" },
];

const INSIGHT_TYPES: Array<{ value: "all" | InsightType; label: string }> = [
  { value: "all", label: "All insight types" },
  { value: "calibration", label: "Calibration" },
  { value: "bias", label: "Bias" },
  { value: "prior", label: "Prior" },
  { value: "pattern", label: "Pattern" },
];

type PagePosition = { key: string; offset: number };
type LoadedPage = { key: string; data: PaginatedResponse<Hypothesis> };

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function BoardPage() {
  const { channel } = useChannel();
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [status, setStatus] = useState<ResearchStatusFilter>("all");
  const [position, setPosition] = useState<PagePosition>({ key: "", offset: 0 });
  const [page, setPage] = useState<LoadedPage | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retry, setRetry] = useState(0);

  const [insightType, setInsightType] = useState<"all" | InsightType>("all");
  const [insights, setInsights] = useState<Insight[]>([]);
  const [insightLoading, setInsightLoading] = useState(true);
  const [insightError, setInsightError] = useState<string | null>(null);
  const [insightHasMore, setInsightHasMore] = useState(false);
  const [insightRetry, setInsightRetry] = useState(0);
  const insightRequestId = useRef(0);

  const requestKey = `${channel}\u0000${deferredSearch.trim()}\u0000${status}`;
  const offset = position.key === requestKey ? position.offset : 0;
  const visiblePage = page?.key === requestKey ? page.data : null;
  const insightScope = `${channel}\u0000${insightType}`;
  const insightScopeRef = useRef(insightScope);

  useLayoutEffect(() => {
    insightScopeRef.current = insightScope;
  }, [insightScope]);

  useEffect(() => {
    let current = true;

    // Loading state describes an external request started by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true);
    setError(null);
    listHypotheses(
      hypothesisListParams({
        channel,
        search: deferredSearch,
        status,
        offset,
        limit: HYPOTHESIS_PAGE_SIZE,
      }),
    )
      .then((data) => {
        if (current) setPage({ key: requestKey, data });
      })
      .catch((reason) => {
        if (current) setError(errorMessage(reason, "Research could not be loaded."));
      })
      .finally(() => {
        if (current) setLoading(false);
      });

    return () => {
      current = false;
    };
  }, [channel, deferredSearch, offset, requestKey, retry, status]);

  useEffect(() => {
    const requestId = ++insightRequestId.current;

    // Loading state describes an external request started by this effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setInsightLoading(true);
    setInsightError(null);
    listInsights({
      ...(channel ? { channel } : {}),
      ...(insightType === "all" ? {} : { type: insightType }),
      offset: 0,
      limit: INSIGHT_PAGE_SIZE + 1,
    })
      .then((items) => {
        if (requestId !== insightRequestId.current || insightScope !== insightScopeRef.current) return;
        setInsights(items.slice(0, INSIGHT_PAGE_SIZE));
        setInsightHasMore(items.length > INSIGHT_PAGE_SIZE);
      })
      .catch((reason) => {
        if (requestId === insightRequestId.current && insightScope === insightScopeRef.current) {
          setInsightError(errorMessage(reason, "Insights could not be loaded."));
        }
      })
      .finally(() => {
        if (requestId === insightRequestId.current && insightScope === insightScopeRef.current) {
          setInsightLoading(false);
        }
      });
  }, [channel, insightRetry, insightScope, insightType]);

  async function loadMoreInsights() {
    const requestId = ++insightRequestId.current;
    const requestScope = insightScope;
    setInsightLoading(true);
    setInsightError(null);

    try {
      const items = await listInsights({
        ...(channel ? { channel } : {}),
        ...(insightType === "all" ? {} : { type: insightType }),
        offset: insights.length,
        limit: INSIGHT_PAGE_SIZE + 1,
      });
      if (requestId !== insightRequestId.current || requestScope !== insightScopeRef.current) return;
      setInsights((current) => [...current, ...items.slice(0, INSIGHT_PAGE_SIZE)]);
      setInsightHasMore(items.length > INSIGHT_PAGE_SIZE);
    } catch (reason) {
      if (requestId === insightRequestId.current && requestScope === insightScopeRef.current) {
        setInsightError(errorMessage(reason, "More insights could not be loaded."));
      }
    } finally {
      if (requestId === insightRequestId.current && requestScope === insightScopeRef.current) {
        setInsightLoading(false);
      }
    }
  }

  const range = visiblePage
    ? pageRange(visiblePage.offset, visiblePage.items.length, visiblePage.total)
    : { first: 0, last: 0 };
  const hasPrevious = Boolean(visiblePage && visiblePage.offset > 0);
  const hasNext = Boolean(
    visiblePage && visiblePage.offset + visiblePage.items.length < visiblePage.total,
  );

  return (
    <div className="mx-auto w-full max-w-[1120px] space-y-10 pb-12">
      <header className="space-y-2">
        <h1 className="text-2xl font-semibold tracking-tight">Research</h1>
        <p className="max-w-2xl text-sm leading-relaxed text-muted-foreground">
          Browse the hypotheses, evidence, and retained insights available to this workspace.
        </p>
      </header>

      <section aria-labelledby="hypotheses-heading">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="hypotheses-heading" className="text-base font-semibold">
              Hypotheses
            </h2>
            <p className="text-xs text-muted-foreground">Newest updates first.</p>
          </div>
          {visiblePage ? (
            <p className="text-xs text-muted-foreground" aria-live="polite">
              {visiblePage.total === 0
                ? "No results"
                : `${range.first}–${range.last} of ${visiblePage.total}`}
            </p>
          ) : null}
        </div>

        <div className="research-toolbar flex flex-col gap-2 border-y py-3 sm:flex-row">
          <label className="sr-only" htmlFor="research-search">
            Search hypotheses
          </label>
          <input
            id="research-search"
            className="h-9 min-w-0 flex-1 rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            type="search"
            placeholder="Search hypotheses"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <label className="sr-only" htmlFor="research-status">
            Filter by status
          </label>
          <select
            id="research-status"
            className="h-9 rounded-md border bg-background px-3 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
            value={status}
            onChange={(event) => setStatus(event.target.value as ResearchStatusFilter)}
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        {error ? (
          <div
            className="research-empty flex items-center justify-between gap-4 border-b py-5 text-sm text-destructive"
            role="alert"
          >
            <span>{error}</span>
            <Button size="sm" variant="outline" onClick={() => setRetry((value) => value + 1)}>
              Retry
            </Button>
          </div>
        ) : null}
        {loading && !visiblePage ? (
          <p className="research-empty border-b py-8 text-sm text-muted-foreground" role="status">
            Loading research…
          </p>
        ) : null}
        {!loading && !error && visiblePage?.items.length === 0 ? (
          <p className="research-empty border-b py-8 text-sm text-muted-foreground">
            No hypotheses match these filters.
          </p>
        ) : null}
        {visiblePage?.items.length ? (
          <div className={`research-list divide-y ${loading ? "opacity-60" : ""}`} aria-busy={loading}>
            {visiblePage.items.map((hypothesis) => (
              <ResearchRow key={hypothesis.id} kind="hypothesis" item={hypothesis} />
            ))}
          </div>
        ) : null}

        {visiblePage && (hasPrevious || hasNext) ? (
          <nav
            className="research-pagination mt-4 flex items-center justify-between"
            aria-label="Hypothesis pages"
          >
            <Button
              size="sm"
              variant="outline"
              disabled={!hasPrevious || loading}
              onClick={() =>
                setPosition({
                  key: requestKey,
                  offset: Math.max(0, offset - HYPOTHESIS_PAGE_SIZE),
                })
              }
            >
              Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              {range.first}–{range.last} of {visiblePage.total}
            </span>
            <Button
              size="sm"
              variant="outline"
              disabled={!hasNext || loading}
              onClick={() =>
                setPosition({ key: requestKey, offset: offset + HYPOTHESIS_PAGE_SIZE })
              }
            >
              Next
            </Button>
          </nav>
        ) : null}
      </section>

      <section className="border-t pt-8" aria-labelledby="insights-heading">
        <div className="mb-3 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 id="insights-heading" className="text-base font-semibold">
              Insights
            </h2>
            <p className="text-xs text-muted-foreground">
              Patterns and lessons retained across the research.
            </p>
          </div>
          <label>
            <span className="sr-only">Filter insights by type</span>
            <select
              className="h-8 rounded-md border bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={insightType}
              onChange={(event) => setInsightType(event.target.value as "all" | InsightType)}
            >
              {INSIGHT_TYPES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
        </div>

        {insightError ? (
          <div
            className="research-empty flex items-center justify-between gap-4 border-b py-5 text-sm text-destructive"
            role="alert"
          >
            <span>{insightError}</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setInsightRetry((value) => value + 1)}
            >
              Retry
            </Button>
          </div>
        ) : null}
        {insightLoading && insights.length === 0 ? (
          <p className="research-empty border-b py-8 text-sm text-muted-foreground" role="status">
            Loading insights…
          </p>
        ) : null}
        {!insightLoading && !insightError && insights.length === 0 ? (
          <p className="research-empty border-b py-8 text-sm text-muted-foreground">
            No insights are available for this selection.
          </p>
        ) : null}
        {insights.length ? (
          <div className="research-list divide-y">
            {insights.map((insight) => (
              <ResearchRow key={insight.id} kind="insight" item={insight} />
            ))}
          </div>
        ) : null}
        {insightHasMore ? (
          <div className="research-pagination pt-4">
            <Button
              size="sm"
              variant="outline"
              disabled={insightLoading}
              onClick={() => void loadMoreInsights()}
            >
              {insightLoading ? "Loading…" : "Load more insights"}
            </Button>
          </div>
        ) : null}
      </section>
    </div>
  );
}
