"use client";

import type { HypothesisStatus } from "@/types/hypothesis";
import { Badge } from "@/components/ui/badge";

const STATUS_VARIANT: Record<HypothesisStatus, { label: string; className: string }> = {
  draft: { label: "Draft", className: "bg-secondary text-secondary-foreground" },
  active: { label: "Active", className: "bg-primary text-primary-foreground" },
  testing: { label: "Testing", className: "bg-amber-500 text-white border-amber-500" },
  supported: { label: "Supported", className: "bg-green-600 text-white border-green-600" },
  refuted: { label: "Refuted", className: "bg-destructive text-white" },
  inconclusive: { label: "Inconclusive", className: "bg-orange-500 text-white border-orange-500" },
  revised: { label: "Revised", className: "bg-purple-600 text-white border-purple-600" },
  archived: { label: "Archived", className: "bg-muted text-muted-foreground" },
};

export function StatusBadge({ status }: { status: HypothesisStatus }) {
  const config = STATUS_VARIANT[status] || STATUS_VARIANT.draft;
  return (
    <Badge variant="outline" className={config.className}>
      {config.label}
    </Badge>
  );
}
