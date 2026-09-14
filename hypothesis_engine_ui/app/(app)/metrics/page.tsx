"use client";

import { useEffect, useState, useCallback } from "react";
import { getMetrics, listAgents } from "@/lib/apiClient";
import { useChannel } from "@/components/channel-provider";
import type { MetricsResponse } from "@/types/hypothesis";
import type { components } from "@/types/api";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { CalibrationChart } from "@/components/metrics/CalibrationChart";
import { BrierSparkline } from "@/components/metrics/BrierSparkline";
import { RigorGauge } from "@/components/metrics/RigorGauge";

type AgentSummary = components["schemas"]["AgentSummary"];

const RATING_COLORS: Record<string, string> = {
  excellent: "bg-green-500/15 text-green-700",
  good: "bg-green-500/10 text-green-600",
  fair: "bg-yellow-500/15 text-yellow-700",
  poor: "bg-red-500/15 text-red-700",
  insufficient_data: "bg-muted text-muted-foreground",
};

const LEARNING_COLORS: Record<string, string> = {
  improving: "text-green-600",
  stable: "text-muted-foreground",
  declining: "text-red-600",
  insufficient_data: "text-muted-foreground",
};

function fmt(v: number | null | undefined, decimals = 2): string {
  if (v == null) return "--";
  return v.toFixed(decimals);
}

function pct(v: number | null | undefined): string {
  if (v == null) return "--";
  return `${Math.round(v * 100)}%`;
}

export default function MetricsPage() {
  const [metrics, setMetrics] = useState<MetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const { channel } = useChannel();
  const [agent, setAgent] = useState<string>("");

  // Load filter options
  useEffect(() => {
    listAgents().then((r) => setAgents(r.agents)).catch(() => {});
  }, []);

  const fetchMetrics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: { channel?: string; created_by?: string } = {};
      if (channel) params.channel = channel;
      if (agent) params.created_by = agent;
      const data = await getMetrics(params);
      setMetrics(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load metrics");
    } finally {
      setLoading(false);
    }
  }, [channel, agent]);

  useEffect(() => {
    // Fetch metrics when an external filter changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchMetrics();
  }, [fetchMetrics]);

  const m = metrics;
  const insufficient = m != null && (m.concluded_count ?? 0) < 2;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-lg font-semibold">Prediction Quality</h1>
          <p className="text-sm text-muted-foreground">
            {m ? `${m.concluded_count ?? 0} concluded of ${m.total_count ?? 0} total` : "Loading..."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Select value={agent || "__all__"} onValueChange={(v) => setAgent(v === "__all__" ? "" : v)}>
            <SelectTrigger className="w-[140px] h-8 text-xs">
              <SelectValue placeholder="All agents" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="__all__">All agents</SelectItem>
              {agents.map((a) => (
                <SelectItem key={a.name} value={a.name ?? "__all__"}>{a.name}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {loading && !m && (
        <div className="text-sm text-muted-foreground py-12 text-center">
          Computing metrics...
        </div>
      )}

      {m && (
        <>
          {/* One-glance summary strip */}
          <div className="flex flex-wrap gap-3">
            <SummaryChip
              label="Brier"
              value={fmt(m.brier?.score, 2)}
              sub={m.brier?.rating ?? ""}
              colorClass={RATING_COLORS[m.brier?.rating ?? "insufficient_data"]}
            />
            <SummaryChip
              label="Cal. Error"
              value={fmt(m.calibration?.calibration_error, 2)}
            />
            <SummaryChip
              label="Bits/pred"
              value={fmt(m.prediction_value?.mean_bits, 1)}
            />
            <SummaryChip
              label="Rigor"
              value={pct(m.falsification?.falsification_coverage)}
            />
            <SummaryChip
              label="Learning"
              value={m.learning_rate?.slope != null ? (m.learning_rate.slope > 0 ? "+" : "") + fmt(m.learning_rate.slope, 4) : "--"}
              sub={m.learning_rate?.interpretation ?? ""}
              colorClass={LEARNING_COLORS[m.learning_rate?.interpretation ?? "insufficient_data"]}
            />
          </div>

          {insufficient && (
            <div className="rounded-lg border border-yellow-500/30 bg-yellow-500/10 p-3 text-sm text-yellow-800">
              Fewer than 2 concluded hypotheses. Metrics will become meaningful as more predictions are resolved.
            </div>
          )}

          {/* Detail cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {/* Brier Score */}
            <Card>
              <CardContent className="p-5 space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                    Brier Score
                  </h3>
                  <Badge variant="secondary" className={`text-[10px] ${RATING_COLORS[m.brier?.rating ?? "insufficient_data"]}`}>
                    {m.brier?.rating}
                  </Badge>
                </div>
                <p className="text-3xl font-bold tabular-nums">
                  {fmt(m.brier?.score, 4)}
                </p>
                <p className="text-xs text-muted-foreground">
                  0 = perfect, 0.25 = coin flip
                </p>
                {(m.brier?.rolling_scores?.length ?? 0) >= 2 && (
                  <BrierSparkline scores={m.brier?.rolling_scores ?? []} />
                )}
              </CardContent>
            </Card>

            {/* Calibration */}
            <Card>
              <CardContent className="p-5 space-y-3">
                <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Calibration
                </h3>
                <p className="text-3xl font-bold tabular-nums">
                  {fmt(m.calibration?.calibration_error, 2)}
                  <span className="text-sm font-normal text-muted-foreground ml-1">error</span>
                </p>
                <CalibrationChart buckets={m.calibration?.buckets ?? []} />
              </CardContent>
            </Card>

            {/* Prediction Value */}
            <Card>
              <CardContent className="p-5 space-y-3">
                <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Prediction Value
                </h3>
                <p className="text-3xl font-bold tabular-nums">
                  {fmt(m.prediction_value?.mean_bits, 2)}
                  <span className="text-sm font-normal text-muted-foreground ml-1">bits/prediction</span>
                </p>
                <p className="text-xs text-muted-foreground">
                  Total: {fmt(m.prediction_value?.total_bits, 1)} bits across {m.prediction_value?.sample_size ?? 0} predictions
                </p>
                <BitsScale value={m.prediction_value?.mean_bits} />
              </CardContent>
            </Card>

            {/* Falsification Rigor */}
            <Card>
              <CardContent className="p-5 space-y-3">
                <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Falsification Rigor
                </h3>
                <RigorGauge
                  evidenceBalance={m.falsification?.evidence_balance_ratio}
                  falsificationCoverage={m.falsification?.falsification_coverage}
                  confidenceReversalRate={m.falsification?.confidence_reversal_rate}
                />
              </CardContent>
            </Card>

            {/* Confidence Dynamics */}
            <Card>
              <CardContent className="p-5 space-y-3">
                <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Confidence Dynamics
                </h3>
                <div className="space-y-2">
                  <DynamicsRow label="Mean drift" value={fmt(m.confidence_dynamics?.mean_absolute_drift, 3)} />
                  <DynamicsRow label="Update magnitude" value={fmt(m.confidence_dynamics?.mean_update_magnitude, 3)} />
                  <DynamicsRow label="Premature conclusions" value={pct(m.confidence_dynamics?.premature_conclusion_rate)} />
                </div>
                <p className="text-[10px] text-muted-foreground mt-2">
                  Drift: |final − initial|. Update: mean |Δ| per evidence.
                </p>
              </CardContent>
            </Card>

            {/* Learning Rate */}
            <Card>
              <CardContent className="p-5 space-y-3">
                <h3 className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                  Learning Rate
                </h3>
                <p className={`text-3xl font-bold tabular-nums ${LEARNING_COLORS[m.learning_rate?.interpretation ?? "insufficient_data"]}`}>
                  {m.learning_rate?.slope != null ? (m.learning_rate.slope > 0 ? "+" : "") + fmt(m.learning_rate.slope, 4) : "--"}
                  <span className="text-sm font-normal ml-1">
                    /batch
                  </span>
                </p>
                <p className="text-xs text-muted-foreground capitalize">
                  {m.learning_rate?.interpretation?.replace("_", " ")}
                </p>
                <p className="text-xs text-muted-foreground">
                  {m.learning_rate?.insight_count ?? 0} insights recorded
                </p>
              </CardContent>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}

function SummaryChip({
  label,
  value,
  sub,
  colorClass,
}: {
  label: string;
  value: string;
  sub?: string;
  colorClass?: string;
}) {
  return (
    <div className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-sm ${colorClass ?? ""}`}>
      <span className="text-muted-foreground text-xs">{label}</span>
      <span className="font-bold tabular-nums">{value}</span>
      {sub && <span className="text-[10px] text-muted-foreground">{sub}</span>}
    </div>
  );
}

function DynamicsRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span className="font-mono font-medium">{value}</span>
    </div>
  );
}

function BitsScale({ value }: { value: number | null | undefined }) {
  const v = value ?? 0;
  const pctVal = Math.min(v / 1.5, 1) * 100;

  const segments = [
    { label: "trivial", end: 20, color: "bg-gray-300" },
    { label: "moderate", end: 47, color: "bg-yellow-400" },
    { label: "high", end: 67, color: "bg-green-500" },
    { label: "bold", end: 100, color: "bg-blue-500" },
  ];

  return (
    <div className="space-y-1">
      <div className="h-2 bg-muted rounded-full overflow-hidden relative">
        {segments.map((s, i) => {
          const prevEnd = i > 0 ? segments[i - 1].end : 0;
          return (
            <div
              key={s.label}
              className={`absolute h-full ${s.color} opacity-20`}
              style={{ left: `${prevEnd}%`, width: `${s.end - prevEnd}%` }}
            />
          );
        })}
        {value != null && (
          <div
            className="absolute h-full bg-foreground/60 rounded-full"
            style={{ width: `${pctVal}%` }}
          />
        )}
      </div>
      <div className="flex justify-between text-[9px] text-muted-foreground">
        <span>0</span>
        <span>0.3</span>
        <span>0.7</span>
        <span>1.0</span>
        <span>1.5+</span>
      </div>
    </div>
  );
}
