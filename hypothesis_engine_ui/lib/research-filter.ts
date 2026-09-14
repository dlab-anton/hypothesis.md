import type { HypothesisStatus } from "@/types/hypothesis";

export type ResearchStatusFilter = "all" | HypothesisStatus;

type HypothesisListFilters = {
  channel: string;
  search: string;
  status: ResearchStatusFilter;
  offset: number;
  limit: number;
};

export function hypothesisListParams({ channel, search, status, offset, limit }: HypothesisListFilters) {
  return {
    ...(channel ? { channel } : {}),
    ...(search.trim() ? { search: search.trim() } : {}),
    ...(status === "archived"
      ? { is_archived: true }
      : status === "all"
        ? {}
        : { status, is_archived: false }),
    sort_by: "updated_at",
    sort_order: "desc",
    offset,
    limit,
  };
}

export function pageRange(offset: number, itemCount: number, total: number) {
  if (total === 0 || itemCount === 0) return { first: 0, last: 0 };
  return { first: offset + 1, last: Math.min(offset + itemCount, total) };
}
