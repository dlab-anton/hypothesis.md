"use client";

import { useState, useEffect, useCallback } from "react";
import { listAgents, getAgentStatus } from "@/lib/apiClient";
import { useChannel } from "@/components/channel-provider";
import { usePolling } from "@/hooks/usePolling";
import { AutoRefreshIndicator } from "@/components/feed/AutoRefreshIndicator";
import { Button } from "@/components/ui/button";
import type { AgentSummary } from "@/types/hypothesis";

export default function StatusPage() {
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [selectedAgent, setSelectedAgent] = useState<string>("");
  const [markdown, setMarkdown] = useState<string>("");
  const [error, setError] = useState<string | null>(null);
  const [agentsLoading, setAgentsLoading] = useState(true);
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
        console.error("Failed to load agents:", e);
        setError(e instanceof Error ? e.message : "Failed to load agents");
      } finally {
        setAgentsLoading(false);
      }
    })();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const fetchStatus = useCallback(async () => {
    if (!selectedAgent) return;
    try {
      setError(null);
      const params: { channel?: string } = {};
      if (channel) params.channel = channel;
      const md = await getAgentStatus(selectedAgent, params);
      setMarkdown(md);
    } catch (e) {
      console.error("Failed to fetch status:", e);
      setError(e instanceof Error ? e.message : "Failed to fetch status report");
    }
  }, [selectedAgent, channel]);

  const { autoRefresh, setAutoRefresh, lastUpdated, loading, refresh } = usePolling(
    fetchStatus,
    { intervalMs: 60_000, storageKey: "he-status-autorefresh" },
  );

  // Re-fetch when selected agent changes (usePolling's initial fetch fires
  // before agents have loaded, so selectedAgent is still "" at that point)
  useEffect(() => {
    if (selectedAgent) refresh();
  }, [selectedAgent]); // eslint-disable-line react-hooks/exhaustive-deps

  if (agentsLoading) {
    return <div className="text-muted-foreground p-8">Loading agents...</div>;
  }

  if (agents.length === 0) {
    return (
      <div className="space-y-4">
        <h1 className="text-2xl font-bold">Status</h1>
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
        <h1 className="text-2xl font-bold">Status</h1>
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
          <p className="font-medium">Failed to load status report</p>
          <p className="mt-1 text-xs opacity-80">{error}</p>
        </div>
      )}

      {/* Raw markdown — shows exactly what the agent reads */}
      {loading && !markdown ? (
        <div className="text-muted-foreground">Generating report...</div>
      ) : markdown ? (
        <pre className="rounded-lg border bg-card p-6 text-sm font-mono whitespace-pre-wrap overflow-x-auto">{markdown}</pre>
      ) : null}
    </div>
  );
}
