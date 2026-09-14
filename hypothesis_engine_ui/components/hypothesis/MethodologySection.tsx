"use client";

import { JsonDisplay } from "./JsonDisplay";
import { formatDeadlineStatus } from "@/lib/timeUtils";
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
    <section className="pt-1" aria-labelledby="methodology-heading">
      <h2 id="methodology-heading" className="text-sm font-semibold">
        Methodology
      </h2>
      <dl className="mt-3 divide-y text-sm">
        {hypothesis.falsification_criteria ? (
          <Field label="Falsification criteria">
            <p className="whitespace-pre-wrap text-muted-foreground">
              {hypothesis.falsification_criteria}
            </p>
          </Field>
        ) : null}
        {hypothesis.null_hypothesis ? (
          <Field label="Null hypothesis (H0)">
            <p className="whitespace-pre-wrap text-muted-foreground">
              {hypothesis.null_hypothesis}
            </p>
          </Field>
        ) : null}
        {hypothesis.significance_level !== null ? (
          <Field label="Significance level">
            {(hypothesis.significance_level * 100).toFixed(
              (hypothesis.significance_level * 100) % 1 === 0 ? 0 : 1,
            )}
            %
          </Field>
        ) : null}
        {hypothesis.experimental_design ? (
          <Field label="Experimental design">
            <JsonDisplay data={hypothesis.experimental_design} />
          </Field>
        ) : null}
        {hypothesis.deadline ? (
          <Field label="Deadline">
            <DeadlineDisplay deadline={hypothesis.deadline} />
          </Field>
        ) : null}
        {hypothesis.metadata && Object.keys(hypothesis.metadata).length > 0 ? (
          <Field label="Metadata">
            <JsonDisplay data={hypothesis.metadata} />
          </Field>
        ) : null}
        {isConcluded && hypothesis.outcome ? (
          <Field label="Outcome">
            <JsonDisplay data={hypothesis.outcome} />
          </Field>
        ) : null}
      </dl>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1 py-3 sm:grid-cols-[10rem_minmax(0,1fr)] sm:gap-4">
      <dt className="text-xs font-medium text-muted-foreground">{label}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
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
      {formatted} <span className={isOverdue ? "text-destructive" : "text-green-700"}>({text})</span>
    </span>
  );
}
