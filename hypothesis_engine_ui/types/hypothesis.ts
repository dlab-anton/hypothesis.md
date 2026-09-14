/**
 * Re-exports from auto-generated OpenAPI types.
 *
 * All types are derived from the backend's OpenAPI spec via openapi-typescript.
 * To regenerate: npm run typegen (requires running backend)
 *           or:  npm run typegen:file (from committed openapi.json)
 */
import type { components } from "./api";

// ── Enums ────────────────────────────────────────────────────────

export type HypothesisStatus = components["schemas"]["HypothesisStatus"];
export type EvidenceType = components["schemas"]["EvidenceType"];
export type InsightType = components["schemas"]["InsightType"];
export type RelationshipType = components["schemas"]["RelationshipType"];

// ── Core Models ─────────────────────────────────────────────────

export type EvidenceCounts = components["schemas"]["EvidenceCounts"];
export type Hypothesis = components["schemas"]["HypothesisRead"];
export type Evidence = components["schemas"]["EvidenceRead"];
export type TimelineEvent = components["schemas"]["EventRead"];
export type StatsResponse = components["schemas"]["StatsResponse"];
export type LineageResponse = components["schemas"]["LineageResponse"];

// ── Input Types ─────────────────────────────────────────────────

export type HypothesisCreateInput = components["schemas"]["HypothesisCreate"];
export type HypothesisUpdateInput = components["schemas"]["HypothesisUpdate"];
export type EvidenceCreateInput = components["schemas"]["EvidenceCreate"];
export type HypothesisReviseInput = components["schemas"]["HypothesisRevise"];

// ── Pagination ──────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

// ── Agent Coordination ──────────────────────────────────────────

export type AgentSummary = components["schemas"]["AgentSummary"];
export type AgentListResponse = components["schemas"]["AgentListResponse"];
export type AgentHypothesisSummary = components["schemas"]["AgentHypothesisSummary"];
export type AgentEvidenceSummary = components["schemas"]["AgentEvidenceSummary"];
export type AgentEventSummary = components["schemas"]["AgentEventSummary"];
export type AgentActivityResponse = components["schemas"]["AgentActivityResponse"];
export type InboxItem = components["schemas"]["InboxItem"];
export type InboxResponse = components["schemas"]["InboxResponse"];

// ── Relationships ───────────────────────────────────────────────

export type Relationship = components["schemas"]["RelationshipRead"];
export type RelationshipCreateInput = components["schemas"]["RelationshipCreate"];
export type NetworkNode = components["schemas"]["NetworkNode"];
export type NetworkEdge = components["schemas"]["NetworkEdge"];
export type NetworkResponse = components["schemas"]["NetworkResponse"];

// ── Insights ────────────────────────────────────────────────────

export type Insight = components["schemas"]["InsightRead"];
export type InsightCreateInput = components["schemas"]["InsightCreate"];
export type InsightUpdateInput = components["schemas"]["InsightUpdate"];

// ── Channels ────────────────────────────────────────────────────

export type Channel = components["schemas"]["ChannelRead"];

// ── API Keys ────────────────────────────────────────────────────

export type ApiKey = components["schemas"]["ApiKeyInfo"];
export type ApiKeyCreateInput = components["schemas"]["ApiKeyCreate"];
export type ApiKeyCreateResponse = components["schemas"]["ApiKeyGenerated"];

// ── Metrics ─────────────────────────────────────────────────────

export type MetricsResponse = components["schemas"]["MetricsResponse"];
export type BrierScoreMetrics = components["schemas"]["BrierScoreMetrics"];
export type CalibrationBucket = components["schemas"]["CalibrationBucket"];
export type CalibrationMetrics = components["schemas"]["CalibrationMetrics"];
export type PredictionValueMetrics = components["schemas"]["PredictionValueMetrics"];
export type FalsificationRigorMetrics = components["schemas"]["FalsificationRigorMetrics"];
export type ConfidenceDynamicsMetrics = components["schemas"]["ConfidenceDynamicsMetrics"];
export type LearningRateMetrics = components["schemas"]["LearningRateMetrics"];
