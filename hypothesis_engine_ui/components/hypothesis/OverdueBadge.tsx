"use client";

import type { Hypothesis } from "@/types/hypothesis";
import { Badge } from "@/components/ui/badge";

const OVERDUE_STATUSES = new Set(["active", "testing"]);

export function isOverdue(h: Hypothesis): boolean {
  return !!(
    h.deadline &&
    OVERDUE_STATUSES.has(h.status) &&
    new Date(h.deadline) < new Date()
  );
}

export function OverdueBadge({ hypothesis }: { hypothesis: Hypothesis }) {
  if (!isOverdue(hypothesis)) return null;
  return (
    <Badge variant="destructive" className="rounded-full text-[10px] px-2 py-0.5">
      Overdue
    </Badge>
  );
}
