import Link from "next/link";
import type { Hypothesis, Insight } from "@/types/hypothesis";
import { STATUS_CONFIG } from "@/lib/constants";
import { formatRelativeTime } from "@/lib/timeUtils";

function evidenceTotal(hypothesis: Hypothesis) {
  const counts = hypothesis.evidence_counts;
  return counts.supporting + counts.contradicting + counts.neutral;
}

type ResearchRowProps =
  | { kind: "hypothesis"; item: Hypothesis }
  | { kind: "insight"; item: Insight };

export function ResearchRow(props: ResearchRowProps) {
  if (props.kind === "insight") {
    const insight = props.item;
    return (
      <Link className="research-row block py-4" href={`/insights/${insight.id}`}>
        <div className="research-title line-clamp-2 whitespace-pre-wrap break-words leading-relaxed">
          {insight.content}
        </div>
        <div className="research-meta mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
          <span>{insight.insight_type}</span>
          <time dateTime={insight.updated_at}>Updated {formatRelativeTime(insight.updated_at)}</time>
          <span>#{insight.channel}</span>
          <span>{insight.created_by}</span>
        </div>
      </Link>
    );
  }

  const hypothesis = props.item;
  const status = hypothesis.is_archived ? "Archived" : STATUS_CONFIG[hypothesis.status].label;
  return (
    <Link className="research-row block py-4" href={`/hypotheses/${hypothesis.id}`}>
      <div className="research-title line-clamp-2 whitespace-normal break-words text-sm font-medium leading-relaxed sm:text-base">
        {hypothesis.statement}
      </div>
      <div className="research-meta mt-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
        <span>{status}</span>
        <span>{evidenceTotal(hypothesis)} evidence</span>
        <time dateTime={hypothesis.updated_at}>
          Updated {formatRelativeTime(hypothesis.updated_at)}
        </time>
        {hypothesis.channel ? <span>#{hypothesis.channel}</span> : null}
        <span>{hypothesis.created_by}</span>
      </div>
    </Link>
  );
}
