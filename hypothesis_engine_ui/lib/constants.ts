import type { HypothesisStatus, EvidenceType } from "@/types/hypothesis";

export const STATUS_CONFIG: Record<HypothesisStatus, { label: string; color: string; bg: string }> = {
  draft: { label: "Draft", color: "text-gray-600", bg: "bg-gray-100" },
  active: { label: "Active", color: "text-blue-600", bg: "bg-blue-100" },
  testing: { label: "Testing", color: "text-amber-600", bg: "bg-amber-100" },
  supported: { label: "Supported", color: "text-green-600", bg: "bg-green-100" },
  refuted: { label: "Refuted", color: "text-red-600", bg: "bg-red-100" },
  inconclusive: { label: "Inconclusive", color: "text-orange-600", bg: "bg-orange-100" },
  revised: { label: "Revised", color: "text-purple-600", bg: "bg-purple-100" },
  archived: { label: "Archived", color: "text-gray-400", bg: "bg-gray-50" },
};

export const EVIDENCE_CONFIG: Record<EvidenceType, { label: string; color: string; border: string; icon: string }> = {
  supporting: { label: "Supporting", color: "text-green-600", border: "border-l-green-500", icon: "+" },
  contradicting: { label: "Contradicting", color: "text-red-600", border: "border-l-red-500", icon: "-" },
  neutral: { label: "Neutral", color: "text-gray-600", border: "border-l-gray-400", icon: "~" },
};

export const EVENT_TYPE_LABELS: Record<string, string> = {
  created: "Created",
  status_changed: "Status Changed",
  confidence_changed: "Confidence Updated",
  confidence_contradiction_warning: "Confirmation Bias Warning",
  evidence_added: "Evidence Added",
  revised: "Revised",
  archived: "Archived",
  unarchived: "Unarchived",
};

export const ALL_STATUSES: HypothesisStatus[] = [
  "draft", "active", "testing", "supported", "refuted", "inconclusive", "revised", "archived",
];

// Deterministic channel color palette — each channel always gets the same color
const CHANNEL_PALETTE = [
  { text: "text-sky-700", bg: "bg-sky-100" },
  { text: "text-violet-700", bg: "bg-violet-100" },
  { text: "text-emerald-700", bg: "bg-emerald-100" },
  { text: "text-rose-700", bg: "bg-rose-100" },
  { text: "text-amber-700", bg: "bg-amber-100" },
  { text: "text-teal-700", bg: "bg-teal-100" },
  { text: "text-fuchsia-700", bg: "bg-fuchsia-100" },
  { text: "text-cyan-700", bg: "bg-cyan-100" },
] as const;

function hashString(s: string): number {
  let hash = 0;
  for (let i = 0; i < s.length; i++) {
    hash = ((hash << 5) - hash + s.charCodeAt(i)) | 0;
  }
  return Math.abs(hash);
}

export function getChannelColor(channel: string): { text: string; bg: string } {
  return CHANNEL_PALETTE[hashString(channel) % CHANNEL_PALETTE.length];
}
