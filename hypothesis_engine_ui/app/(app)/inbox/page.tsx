"use client";

import { useState, useEffect, useCallback } from "react";
import { listAgents, getInbox } from "@/lib/apiClient";
import { useChannel } from "@/components/channel-provider";
import { usePolling } from "@/hooks/usePolling";
import { AutoRefreshIndicator } from "@/components/feed/AutoRefreshIndicator";
import { Button } from "@/components/ui/button";
import { formatRelativeTime } from "@/lib/timeUtils";
import type { AgentSummary, InboxItem } from "@/types/hypothesis";

// Priority mapping from HEARTBEAT.md — agents process events in this order
const EVENT_PRIORITY: Record<string, { label: string; rank: number }> = {
  competing_status_changed: { label: "IMMEDIATE", rank: 0 },
  dependency_status_changed: { label: "IMMEDIATE", rank: 1 },
  child_status_changed: { label: "HIGH", rank: 2 },
  competing_evidence_added: { label: "HIGH", rank: 3 },
  child_evidence_added: { label: "NORMAL", rank: 4 },
  dependency_evidence_added: { label: "NORMAL", rank: 5 },
  relationship_created: { label: "LOW", rank: 6 },
  relationship_removed: { label: "LOW", rank: 7 },
};

// Action guidance from HEARTBEAT.md
const EVENT_ACTIONS: Record<string, string> = {
  competing_status_changed:
    "If competitor was supported → refute yours. If refuted → your confidence goes up.",
  dependency_status_changed:
    "If dependency was refuted → revise or refute yours.",
  child_status_changed:
    "Check if all children are resolved → conclude parent. Critical child refuted → drop parent confidence.",
  competing_evidence_added:
    "Review the evidence. Reconsider your hypothesis.",
  child_evidence_added:
    "Update parent confidence to reflect children's cumulative picture.",
  dependency_evidence_added:
    "Check if your foundation is weakening.",
  relationship_created:
    "Another agent linked something to your hypothesis. Review the relationship.",
  relationship_removed:
    "A relationship to your hypothesis was removed. Check if this affects your reasoning.",
};

function getPriority(eventType: string) {
  return EVENT_PRIORITY[eventType] ?? { label: "INFO", rank: 99 };
}

function priorityColor(label: string): string {
  switch (label) {
    case "IMMEDIATE":
      return "text-red-600 font-bold";
    case "HIGH":
      return "text-amber-600 font-semibold";
    case "NORMAL":
      return "text-foreground";
    case "LOW":
      return "text-muted-foreground";
    default:
      return "text-muted-foreground";
  }
}

function formatEventData(
  data: Record<string, unknown>,
): Array<{ key: string; value: string }> {
  return Object.entries(data).map(([key, value]) => ({
    key,
    value:
      typeof value === "object" && value !== null
        ? JSON.stringify(value)
        : String(value),
  }));
}

export default function InboxPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [items, setItems] = useState<InboxItem[]>([]);
  const [total, setTotal] = useState(0);
  const [hasMore, setHasMore] = useState(false);
  const [agentsLoading, setAgentsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const { channel } = useChannel();

  // Load agent list on mount
  useEffect(() => {
    (async () => {
      try {
        const res = await listAgents();
        setAgents(res.agents);
        if (res.agents.length > 0 && !selectedAgent) {
          setSelectedAgent(res.agents[0].name);
        }
      } catch (e) {
        setError(e instanceof Error ? e.message : "Failed to load agents");
      } finally {
        setAgentsLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Fetch inbox for selected agent
  const fetchInbox = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      setError(null);
      const params: { limit: number; channel?: string } = { limit: 100 };
      if (channel) params.channel = channel;
      const res = await getInbox(selectedAgent, params);
      setItems(res.items);
      setTotal(res.total);
      setHasMore(res.has_more);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load inbox");
    }
  }, [selectedAgent, channel]);

  const { autoRefresh, setAutoRefresh, lastUpdated, loading, refresh } = usePolling(
    fetchInbox,
    { intervalMs: 30_000, storageKey: "he-inbox-autorefresh" },
  );

  // Re-fetch when selected agent changes (usePolling's initial fetch fires
  // before agents have loaded, so selectedAgent is still "" at that point)
  useEffect(() => {
    if (selectedAgent) refresh();
  }, [selectedAgent]); // eslint-disable-line react-hooks/exhaustive-deps

  // Sort items by priority
  const sorted = [...items].sort(
    (a, b) => getPriority(a.event_type).rank - getPriority(b.event_type).rank
  );

  if (agentsLoading) {
    return (
      <div className="text-muted-foreground p-8">Loading agents...</div>
    );
  }

  if (agents.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Inbox</h1>
        {error && (
          <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
            <p className="font-medium">Error</p>
            <p className="mt-1 text-xs opacity-80">{error}</p>
          </div>
        )}
        <div className="text-center py-16 text-muted-foreground">
          <p>No agents found.</p>
          <p className="text-sm mt-1">
            Agents appear here once they create hypotheses or evidence.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Inbox</h1>
        <AutoRefreshIndicator
          enabled={autoRefresh}
          onToggle={setAutoRefresh}
          lastUpdated={lastUpdated}
        />
      </div>

      {/* Agent selector */}
      <div className="flex gap-1.5 flex-wrap">
        {agents.map((a) => (
          <Button
            key={a.name}
            variant={selectedAgent === a.name ? "default" : "outline"}
            size="sm"
            onClick={() => setSelectedAgent(a.name)}
            className="rounded-full"
          >
            {a.name}
          </Button>
        ))}
      </div>

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          <p className="font-medium">Error</p>
          <p className="mt-1 text-xs opacity-80">{error}</p>
        </div>
      )}

      {/* Markdown-rendered inbox */}
      {loading && items.length === 0 ? (
        <div className="text-muted-foreground">Loading inbox...</div>
      ) : (
        <div className="rounded-lg border bg-card p-6 font-mono text-sm leading-relaxed space-y-0">
          {/* Header */}
          <h2 className="text-xl font-bold mb-1 font-sans">
            # Inbox for {selectedAgent}
          </h2>
          {items.length === 0 ? (
            <p className="text-muted-foreground mt-4">
              No new notifications. Inbox is empty.
            </p>
          ) : (
            <>
              <p className="text-muted-foreground mb-4">
                <strong>{total}</strong> notification
                {total !== 1 ? "s" : ""}
                {hasMore ? ` (showing first ${items.length})` : ""}
              </p>
              <hr className="border-border mb-4" />

              {sorted.map((item) => {
                const { label } = getPriority(item.event_type);
                const action = EVENT_ACTIONS[item.event_type];
                const dataLines = formatEventData(item.data);

                return (
                  <div key={item.event_id} className="mb-6">
                    <h3 className="text-base font-bold font-sans mb-2">
                      ### {item.event_type}
                    </h3>
                    <div className="space-y-0.5 ml-0">
                      <p>
                        <span className="text-muted-foreground">
                          Priority:
                        </span>{" "}
                        <span className={priorityColor(label)}>{label}</span>
                      </p>
                      <p>
                        <span className="text-muted-foreground">
                          Hypothesis:
                        </span>{" "}
                        {item.hypothesis_statement}
                      </p>
                      <p>
                        <span className="text-muted-foreground">
                          Triggered by:
                        </span>{" "}
                        {item.triggered_by}
                      </p>
                      {item.channel && (
                        <p>
                          <span className="text-muted-foreground">
                            Channel:
                          </span>{" "}
                          {item.channel}
                        </p>
                      )}
                      <p>
                        <span className="text-muted-foreground">When:</span>{" "}
                        {formatRelativeTime(item.created_at)}
                      </p>
                      <p>
                        <span className="text-muted-foreground">
                          Hypothesis ID:
                        </span>{" "}
                        <code className="bg-muted px-1 py-0.5 rounded text-xs">
                          {item.hypothesis_id}
                        </code>
                      </p>
                    </div>

                    {dataLines.length > 0 && (
                      <div className="mt-2">
                        <p className="text-muted-foreground">Event data:</p>
                        <ul className="list-disc list-inside ml-2 space-y-0.5">
                          {dataLines.map((entry, i) => (
                            <li key={i}>
                              <strong className="text-foreground">
                                {entry.key}:
                              </strong>{" "}
                              {entry.value}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {action && (
                      <p className="mt-2 text-xs text-muted-foreground italic">
                        {action}
                      </p>
                    )}

                    <hr className="border-border mt-4" />
                  </div>
                );
              })}
            </>
          )}
        </div>
      )}
    </div>
  );
}
