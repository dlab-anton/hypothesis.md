import { client, API_BASE, STORAGE_KEY, getApiKey, handleAuthFailure } from "./api";
import type { paths, components } from "@/types/api";

// Re-export for consumers (auth-guard, app-sidebar)
export { API_BASE, STORAGE_KEY, getApiKey, handleAuthFailure };

// ── Error handling ──────────────────────────────────────────────

/** Extract error message from openapi-fetch error and throw. */
function throwOnError({ error, response }: { error: unknown; response: Response }): never {
  if (typeof error === "object" && error !== null && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") throw new Error(detail);
    // FastAPI validation errors: [{msg, loc, type}, ...]
    if (Array.isArray(detail))
      throw new Error(detail.map((d: { msg: string }) => d.msg).join(", "));
  }
  throw new Error(`HTTP ${response.status}`);
}

// ── Query param types (extracted from generated paths) ──────────

type ListHypothesesQuery = paths["/api/v1/hypotheses"]["get"]["parameters"]["query"];
type ListInsightsQuery = paths["/api/v1/insights"]["get"]["parameters"]["query"];
type ListChannelsQuery = paths["/api/v1/channels"]["get"]["parameters"]["query"];
type AgentActivityQuery = paths["/api/v1/agents/{agent_name}/activity"]["get"]["parameters"]["query"];
type InboxQuery = paths["/api/v1/inbox"]["get"]["parameters"]["query"];

// ── Hypotheses ───────────────────────────────────────────────────

export async function createHypothesis(
  data: components["schemas"]["HypothesisCreate"],
) {
  const result = await client.POST("/api/v1/hypotheses", { body: data });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function listHypotheses(params?: ListHypothesesQuery) {
  const result = await client.GET("/api/v1/hypotheses", {
    params: { query: params },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getHypothesis(id: string) {
  const result = await client.GET("/api/v1/hypotheses/{hypothesis_id}", {
    params: { path: { hypothesis_id: id } },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function updateHypothesis(
  id: string,
  data: components["schemas"]["HypothesisUpdate"],
) {
  const result = await client.PATCH("/api/v1/hypotheses/{hypothesis_id}", {
    params: { path: { hypothesis_id: id } },
    body: data,
  });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function archiveHypothesis(id: string) {
  const result = await client.DELETE("/api/v1/hypotheses/{hypothesis_id}", {
    params: { path: { hypothesis_id: id } },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getStats() {
  const result = await client.GET("/api/v1/hypotheses/stats");
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getMetrics(params?: { channel?: string; created_by?: string }) {
  const result = await client.GET("/api/v1/hypotheses/metrics", {
    params: { query: params },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

// ── Evidence ─────────────────────────────────────────────────────

export async function addEvidence(
  hypothesisId: string,
  data: components["schemas"]["EvidenceCreate"],
) {
  const result = await client.POST(
    "/api/v1/hypotheses/{hypothesis_id}/evidence",
    { params: { path: { hypothesis_id: hypothesisId } }, body: data },
  );
  if (result.error) throwOnError(result);
  return result.data;
}

export async function listEvidence(
  hypothesisId: string,
  evidenceType?: components["schemas"]["EvidenceType"],
  offset = 0,
) {
  const result = await client.GET(
    "/api/v1/hypotheses/{hypothesis_id}/evidence",
    {
      params: {
        path: { hypothesis_id: hypothesisId },
        query: {
          ...(evidenceType ? { evidence_type: evidenceType } : {}),
          offset,
          limit: 20,
        },
      },
    },
  );
  if (result.error) throwOnError(result);
  return result.data.items;
}

// ── Timeline & Lineage ──────────────────────────────────────────

export async function getTimeline(hypothesisId: string) {
  const result = await client.GET(
    "/api/v1/hypotheses/{hypothesis_id}/timeline",
    { params: { path: { hypothesis_id: hypothesisId } } },
  );
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getLineage(hypothesisId: string) {
  const result = await client.GET(
    "/api/v1/hypotheses/{hypothesis_id}/lineage",
    { params: { path: { hypothesis_id: hypothesisId } } },
  );
  if (result.error) throwOnError(result);
  return result.data;
}

export async function reviseHypothesis(
  hypothesisId: string,
  data: components["schemas"]["HypothesisRevise"],
) {
  const result = await client.POST(
    "/api/v1/hypotheses/{hypothesis_id}/revise",
    { params: { path: { hypothesis_id: hypothesisId } }, body: data },
  );
  if (result.error) throwOnError(result);
  return result.data;
}

// ── Agents ──────────────────────────────────────────────────────

export async function listAgents() {
  const result = await client.GET("/api/v1/agents");
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getAgentActivity(
  name: string,
  params?: AgentActivityQuery,
) {
  const result = await client.GET("/api/v1/agents/{agent_name}/activity", {
    params: { path: { agent_name: name }, query: params },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getInbox(
  agent: string,
  params?: Omit<NonNullable<InboxQuery>, "agent">,
) {
  const result = await client.GET("/api/v1/inbox", {
    params: { query: { agent, ...params } },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

export async function getAgentStatus(name: string, params?: { channel?: string }): Promise<string> {
  const result = await client.GET("/api/v1/agents/{agent_name}/status", {
    params: { path: { agent_name: name }, query: params },
    parseAs: "text",
  });
  if (result.error) throwOnError(result);
  return result.data;
}

// ── Insights ────────────────────────────────────────────────────

export async function listInsights(params?: ListInsightsQuery) {
  const result = await client.GET("/api/v1/insights", {
    params: { query: params },
  });
  if (result.error) throwOnError(result);
  return result.data.items;
}

export async function getInsight(id: string) {
  const result = await client.GET("/api/v1/insights/{insight_id}", {
    params: { path: { insight_id: id } },
  });
  if (result.error) throwOnError(result);
  return result.data;
}

// ── Channels ────────────────────────────────────────────────────

export async function listChannels(params?: ListChannelsQuery) {
  const result = await client.GET("/api/v1/channels", {
    params: { query: params },
  });
  if (result.error) throwOnError(result);
  return result.data.items;
}

export async function getChannel(name: string) {
  const result = await client.GET("/api/v1/channels/{name}", {
    params: { path: { name } },
  });
  if (result.error) throwOnError(result);
  return result.data;
}
