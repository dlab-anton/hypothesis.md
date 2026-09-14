"use client";

import { Collapsible, CollapsibleTrigger, CollapsibleContent } from "@/components/ui/collapsible";
import { JsonDisplay } from "./JsonDisplay";
import { formatDeadlineStatus } from "@/lib/timeUtils";
import { ChevronDown } from "lucide-react";
import type { Hypothesis } from "@/types/hypothesis";

export function MethodologySection({ hypothesis }: { hypothesis: Hypothesis }) {
  const hasContent =
    hypothesis.falsification_criteria ||
    hypothesis.null_hypothesis ||
    hypothesis.significance_level !== null ||
    hypothesis.experimental_design ||
    hypothesis.deadline ||
    hypothesis.metadata ||
    hypothesis.outcome;

  if (!hasContent) return null;

  const isConcluded = ["supported", "refuted", "inconclusive"].includes(hypothesis.status);

  return (
    <Collapsible defaultOpen>
      <CollapsibleTrigger className="flex items-center gap-2 text-sm font-medium hover:text-foreground transition-colors group w-full">
        <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-data-[state=closed]:-rotate-90" />
        Methodology
      </CollapsibleTrigger>
      <CollapsibleContent>
        <div className="mt-2 space-y-3 pl-6 text-sm">
          {hypothesis.falsification_criteria && (
            <Field label="Falsification Criteria">
              <p className="italic text-muted-foreground">&ldquo;{hypothesis.falsification_criteria}&rdquo;</p>
            </Field>
          )}

          {hypothesis.null_hypothesis && (
            <Field label="Null Hypothesis (H0)">
              <p className="italic text-muted-foreground">&ldquo;{hypothesis.null_hypothesis}&rdquo;</p>
            </Field>
          )}

          {hypothesis.significance_level !== null && (
            <Field label="Significance Level">
              <span>{(hypothesis.significance_level * 100).toFixed(hypothesis.significance_level * 100 % 1 === 0 ? 0 : 1)}%</span>
            </Field>
          )}

          {hypothesis.experimental_design && (
            <Field label="Experimental Design">
              <JsonDisplay data={hypothesis.experimental_design} />
            </Field>
          )}

          {hypothesis.deadline && (
            <Field label="Deadline">
              <DeadlineDisplay deadline={hypothesis.deadline} />
            </Field>
          )}

          {hypothesis.metadata && Object.keys(hypothesis.metadata).length > 0 && (
            <Field label="Metadata">
              <JsonDisplay data={hypothesis.metadata} />
            </Field>
          )}

          {isConcluded && hypothesis.outcome && (
            <Field label="Outcome">
              <div className={`border-l-4 pl-3 ${
                hypothesis.status === "supported" ? "border-l-green-500" :
                hypothesis.status === "refuted" ? "border-l-red-500" :
                "border-l-orange-500"
              }`}>
                <JsonDisplay data={hypothesis.outcome} />
              </div>
            </Field>
          )}
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs font-medium text-muted-foreground mb-0.5">{label}</div>
      {children}
    </div>
  );
}

function DeadlineDisplay({ deadline }: { deadline: string }) {
  const { text, isOverdue } = formatDeadlineStatus(deadline);
  const formatted = new Date(deadline).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
  return (
    <span>
      {formatted}{" "}
      <span className={isOverdue ? "text-destructive" : "text-green-600"}>({text})</span>
    </span>
  );
}
