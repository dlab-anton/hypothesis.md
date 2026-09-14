"use client";

interface GaugeBarProps {
  label: string;
  value: number | null | undefined;
  format?: (v: number) => string;
  thresholds?: { green: number; yellow: number };
  invert?: boolean;
}

function GaugeBar({
  label,
  value,
  format = (v) => `${Math.round(v * 100)}%`,
  thresholds = { green: 0.6, yellow: 0.3 },
  invert = false,
}: GaugeBarProps) {
  const pct = value != null ? Math.min(value, 1) * 100 : 0;
  const hasValue = value != null;

  let color = "bg-red-500";
  if (hasValue) {
    const v = invert ? 1 - value : value;
    if (v >= thresholds.green) color = "bg-green-500";
    else if (v >= thresholds.yellow) color = "bg-yellow-500";
  }

  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-mono font-medium">
          {hasValue ? format(value) : "--"}
        </span>
      </div>
      <div className="h-2 bg-muted rounded-full overflow-hidden">
        {hasValue && (
          <div
            className={`h-full rounded-full transition-all ${color}`}
            style={{ width: `${pct}%` }}
          />
        )}
      </div>
    </div>
  );
}

interface Props {
  evidenceBalance: number | null | undefined;
  falsificationCoverage: number | null | undefined;
  confidenceReversalRate: number | null | undefined;
}

export function RigorGauge({
  evidenceBalance,
  falsificationCoverage,
  confidenceReversalRate,
}: Props) {
  return (
    <div className="space-y-3">
      <GaugeBar
        label="Evidence balance"
        value={evidenceBalance}
        thresholds={{ green: 0.2, yellow: 0.1 }}
      />
      <GaugeBar
        label="Falsification criteria"
        value={falsificationCoverage}
        thresholds={{ green: 0.8, yellow: 0.5 }}
      />
      <GaugeBar
        label="Confidence reversals"
        value={confidenceReversalRate}
        thresholds={{ green: 0.3, yellow: 0.15 }}
      />
    </div>
  );
}
