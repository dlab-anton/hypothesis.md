---
name: hypothesis-engine
description: "Structured reasoning under uncertainty. Form predictions before investigating, test them by seeking disconfirmation, update confidence from evidence, and build domain knowledge that persists across sessions. Use for any task where being wrong is expensive: debugging, research, forecasting, decision-making."
---

# Hypothesis

Predict, test, update. Form predictions before investigating, test them against evidence by trying to prove them wrong, update your confidence, and build domain knowledge that persists across sessions.

**When NOT to use:** Don't track hypotheses for factual lookups, simple calculations, or tasks with no genuine uncertainty. If you already know the answer or can verify it in one step, just do it.

## Setup

Your operator gives you the API base URL. Set it as an environment variable (or store it however you persist configuration):

```
HYPOTHESIS_API=https://your-api-host.com/api/v1
```

### First time: Create a workspace and API key

**Important: Ask the human for approval before generating a key.** Tell them you need to create a workspace and API key, and where you plan to store it. Do not run the key creation request until they confirm.

Once approved — no authentication required. This creates a new isolated workspace:

```bash
curl -sL -X POST "$HYPOTHESIS_API/keys" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-agent"}' | jq
```

Response:

```json
{"id": "uuid", "key": "he_abc123...", "label": "my-agent", "tenant_id": "uuid"}
```

**Save the `key` value immediately** — it is shown only once and cannot be retrieved later. Store it wherever you persist configuration between sessions (e.g. environment variable, `.env` file, `CLAUDE.md`, local config):

```
HYPOTHESIS_KEY=he_abc123...
```

### Joining an existing workspace

A workspace ID identifies the workspace; it does not grant access. Your operator
can securely issue you a key, or authorize you to create another labeled key
using an existing active key from that same workspace. **Ask the human for
approval before generating the key**, same as above. Never request or distribute
the server master key for ordinary agent onboarding.

```bash
curl -sL -X POST "$HYPOTHESIS_API/keys" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-agent", "tenant_id": "WORKSPACE_ID_FROM_OPERATOR"}' | jq
```

All agents with workspace access see its hypotheses, evidence, and events.
`created_by` preserves caller-supplied attribution; it does not grant permission
or prove a separate human identity. Motive contributors use Motive's project key
and documented gateway, rather than minting direct engine credentials.

### Verify connection

```bash
curl -sL "$HYPOTHESIS_API/health" | jq
```

### Define your channel

A channel is a domain scope with a stated goal. Set `channel` on hypotheses and insights to organize by domain. Check existing channels first, create one if your domain isn't covered:

```bash
curl -sL "$HYPOTHESIS_API/channels" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Create a channel (if needed)
curl -sL -X POST "$HYPOTHESIS_API/channels" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "my-domain", "goal": "What this channel tracks and predicts", "created_by": "my-agent"}' | jq
```

Channel design guide (when to split, merge, or scope channels): [CHANNELS.md](references/CHANNELS.md)

---

## The Loop

Start with **prediction**, not observation. State what you expect, then check reality. Reactive agents accumulate anecdotes; predictive agents accumulate knowledge.

```
1. PREDICT   — What do I expect to find? State it before looking.
2. OBSERVE   — Look. Compare reality to prediction.
3. COMPARE   — Prediction error? That's a hypothesis.
4. DECOMPOSE — Broad or multi-causal? Break into testable sub-hypotheses.
               Multiple explanations? Create competitors.
5. FALSIFY   — State what would disprove it. Can't? It's not testable.
6. TEST      — Move to testing. Seek disconfirming evidence FIRST.
7. RECORD    — Add ALL evidence: supporting, contradicting, neutral.
8. UPDATE    — Update confidence after each piece of evidence.
9. CONCLUDE  — supported, refuted, or inconclusive. Must include `outcome`.
10. LEARN    — Record insights (calibration, bias, prior, pattern).
11. ARCHIVE  — DELETE the concluded hypothesis to keep the board clean.
12. REVISE   — If the claim needs to change, revise with rationale.
```

Every step is recorded. You focus on thinking; the system handles the audit trail.

---

## Hypothesis Lifecycle

```
draft → active → testing → supported → archived
                         → refuted   → archived
                         → inconclusive → revised (new hypothesis)
```

**You cannot skip testing.** `active` can only transition to `testing` (or `archived`). Conclusions require going through `testing` first.

**Terminal states are permanent.** `supported`, `refuted`, `inconclusive`, and `revised` cannot be changed back to `testing` or `active`. The API will reject the transition. If you concluded too early, use `/revise` to create a corrected hypothesis — the original stays as a permanent record of your reasoning.

- `draft` — Initial idea, not yet formalized
- `active` — Falsification criteria defined, ready for investigation
- `testing` — Actively gathering evidence and attempting to invalidate
- `supported` — Survived genuine attempts at invalidation
- `refuted` — Falsification criteria met or contradicting evidence decisive
- `inconclusive` — Tested but evidence insufficient to conclude
- `revised` — Replaced by a refined hypothesis (terminal)
- `archived` — Soft-deleted, recoverable

---

## Quick Reference

| Action | Method | Endpoint |
|--------|--------|----------|
| Create hypothesis | POST | `/hypotheses` |
| List hypotheses | GET | `/hypotheses` |
| Get hypothesis | GET | `/hypotheses/:id` |
| Read hypothesis + evidence within a pinned channel | GET | `/channels/:name/context/hypotheses/:id?expected_channel_id=:channelId&evidence_offset=0` |
| Update hypothesis | PATCH | `/hypotheses/:id` |
| Archive hypothesis | DELETE | `/hypotheses/:id` |
| Add evidence | POST | `/hypotheses/:id/evidence` |
| List evidence | GET | `/hypotheses/:id/evidence` |
| Revise hypothesis | POST | `/hypotheses/:id/revise` |
| View lineage | GET | `/hypotheses/:id/lineage` |
| View timeline | GET | `/hypotheses/:id/timeline` |
| Dashboard stats | GET | `/hypotheses/stats` |
| Create relationship | POST | `/hypotheses/:id/relationships` |
| List relationships | GET | `/hypotheses/:id/relationships` |
| Delete relationship | DELETE | `/hypotheses/:id/relationships/:rel_id` |
| View network | GET | `/hypotheses/:id/network` |
| List agents | GET | `/agents` |
| Agent activity | GET | `/agents/:name/activity` |
| Agent status report | GET | `/agents/:name/status` |
| Agent inbox | GET | `/inbox?agent=:name` |
| Create insight | POST | `/insights` |
| List insights | GET | `/insights` |
| Get insight | GET | `/insights/:id` |
| Update insight | PATCH | `/insights/:id` |
| Delete insight | DELETE | `/insights/:id` |
| Create channel | POST | `/channels` |
| List channels | GET | `/channels` |
| Get channel | GET | `/channels/:name` |
| Update channel | PATCH | `/channels/:name` |
| Delete channel | DELETE | `/channels/:name` |
| Generate API key | POST | `/keys` |
| Health check | GET | `/health` |

All endpoints require `X-API-Key` header except `/health`, `/SKILL.md`, `/skill/version`, and `POST /keys`.

**Response shapes:** `POST` returns the created object directly. `GET` list endpoints return `{"items": [...], "total": N, "offset": N, "limit": N}`. `GET` single-resource endpoints return the object directly. `DELETE` returns `204 No Content`.

### Your First Hypothesis

Copy-paste this. Replace `$HYPOTHESIS_API` and `$HYPOTHESIS_KEY` with your values:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "statement": "Restarting the service will fix the 503 errors",
  "context": "Users reporting intermittent 503s since last deploy",
  "falsification_criteria": "If 503s persist after restart, this is refuted",
  "status": "active",
  "confidence": 0.5,
  "tags": ["infra", "incident"],
  "channel": "ops",
  "created_by": "my-agent"
}' | jq
```

**Required fields:** `statement`, `created_by`. Everything else is optional but `falsification_criteria`, `status`, `confidence`, `channel`, and `tags` are strongly recommended.

### Add Evidence

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "content": "503 rate dropped from 12% to 0.1% within 2 minutes of restart",
  "evidence_type": "supporting",
  "strength": 0.8,
  "source": "datadog dashboard",
  "created_by": "my-agent",
  "confidence": 0.75
}' | jq
```

**`evidence_type`**: `supporting`, `contradicting`, or `neutral`. **`strength`**: 0.0–1.0. **`confidence`** (optional): updates the hypothesis confidence in the same call.

### Revise a Hypothesis

Use when the core claim needs to change, or you concluded too early and need to correct course. Creates a new hypothesis linked to the original via `parent_id`.

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ID/revise" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "statement": "Restarting the service reduces 503 errors but does not eliminate them",
  "rationale": "Original hypothesis was premature — 503s returned within 4 hours of restart",
  "created_by": "my-agent"
}' | jq
```

**Required fields:** `statement`, `rationale`, `created_by`. The original hypothesis is marked `revised` (terminal) and the new one starts as `draft`.

For full curl examples and response formats, see [REFERENCE.md](references/REFERENCE.md).

For periodic review and hypothesis maintenance, see [HEARTBEAT.md](references/HEARTBEAT.md).

---

## The Heartbeat

**Run at session start, every 30–60 minutes, and before ending a session.**

```
0. GET /channels/$CHANNEL                 → Load channel goal (stay aligned)
   GET /insights?channel=$CHANNEL         → Load priors, biases, calibration
1. GET /inbox?agent=$AGENT_NAME           → Process events (highest priority first)
2. GET /hypotheses?status=testing          → Check deadlines, conclude or extend
   &created_by=$AGENT_NAME
3. For each parent: GET /$ID/network      → Update parent from children
4. Check competing clusters               → Refute losers, break deadlocks
5. Scan confidence values                  → Audit 0.9+, zero-contradiction
6. POST /insights (if patterns found)      → Record calibration/bias/prior/pattern
7. DELETE concluded hypotheses             → Archive after insights extracted
```

Full routine with action patterns: [HEARTBEAT.md](references/HEARTBEAT.md).

---

## Structured Reasoning

### Decompose (`decomposes_into`)

Decompose when a hypothesis is broad, multi-causal, or has independently verifiable components. Test at the leaf level.

```
"API is slow" (too broad)
  ├── "DB queries exceed 200ms on /users" (testable)
  ├── "Connection pool saturates at 50 concurrent" (testable)
  └── "JSON serialization blocks event loop" (testable)
```

**Rule:** If your hypothesis contains "and"/"or" or describes a phenomenon rather than a mechanism, decompose it.

### Compete (`competes_with`)

Create competitors when there are multiple possible explanations. Forces you to reason about alternatives instead of fixating on your first guess.

```
Observation: "Build times doubled"
  A: "New dep pulls 200MB transitive deps" (competes_with B, C)
  B: "CI cache invalidated by Node bump" (competes_with A, C)
  C: "Test suite grew 40% from generated tests" (competes_with A, B)
```

**Rule:** If you immediately have "a theory," create at least one alternative. Your first explanation is a cached pattern, not a conclusion.

### Depend (`depends_on`)

Use when one hypothesis is only meaningful if another is true.

```
"Feature flag caused the spike" (depends_on →)
  "Latency spike exists and isn't a monitoring artifact"
```

### Responding to propagated events

| Event | Action |
|-------|--------|
| `child_evidence_added` | Update parent confidence to reflect children's picture. |
| `child_status_changed` | All resolved → conclude parent. Critical child refuted → parent < 0.5. |
| `competing_evidence_added` | Re-evaluate. Evidence for an alternative is evidence against yours. |
| `competing_status_changed` | Competitor supported → refute yours (mutual exclusivity). |
| `dependency_status_changed` | Dependency refuted → revise or refute yours. |

---

## Confidence Calibration

| Confidence | Meaning |
|------------|---------|
| 0.1–0.2 | Speculation. Hunch, no evidence. |
| 0.3–0.4 | Weak signal. One piece of indirect evidence. |
| 0.5 | Coin flip. Default start for new hypotheses. |
| 0.6–0.7 | Moderate. Multiple supporting, no contradictions. |
| 0.8 | Strong. Independent sources agree, disconfirming search found nothing. |
| 0.9+ | Near-certain. Must justify explicitly. |

**Rules:**

- Start at 0.5 unless channel insights provide a specific prior.
- Move in small increments (0.05–0.15 per evidence).
- Contradicting evidence should hurt more than supporting evidence helps.
- 0.9+ requires naming what you checked and didn't find.
- If confidence only went up, you were confirming, not testing.

**Hierarchical confidence** (when hypothesis has children via `decomposes_into`):

- Parent ≤ weighted average of children.
- Refuted critical child → parent < 0.5.
- Untested children → parent still uncertain.

---

## Falsification Protocol

Before marking any hypothesis `supported`, answer YES to all:

1. Did I state `falsification_criteria` before testing?
2. Did I search for evidence matching those criteria?
3. Did I record at least one contradicting or neutral evidence?
4. Did I check competing hypotheses? If none, did I create one?
5. Did confidence move DOWN at any point? (If not, I was confirming.)

If any answer is no, mark `inconclusive` and go back.

The system flags contradicting evidence + rising confidence (`confidence_contradiction_warning`). But it can't flag never looking for contradicting evidence. That's on you.

---

## When to Stop Testing

**Supported:** Searched for disconfirming evidence per falsification criteria and didn't find it. At least one contradicting evidence recorded (proving you looked). Multiple independent sources agree. Confidence > 0.7.

**Refuted:** Evidence matching falsification criteria found. Competitor supported (mutual exclusivity). Dependency refuted. Confidence < 0.3.

**Inconclusive:** Couldn't find evidence either way. Evidence balanced and contradictory. Hypothesis too vague to test as stated. Deadline passed.

**`outcome` is required when concluding.** The API will reject a transition to `supported`, `refuted`, or `inconclusive` without an `outcome` object. Include it in the PATCH request:

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "status": "supported",
  "confidence": 0.85,
  "outcome": {
    "result": "supported",
    "narrative": "503 errors resolved after restart and did not recur over 48h monitoring window",
    "evidence_summary": "3 supporting, 1 contradicting (brief spike at +6h, resolved)",
    "source": "Datadog APM dashboard, 48h error rate graph"
  },
  "created_by": "my-agent"
}' | jq
```

The `outcome` object is freeform — use whatever fields make sense for your domain. **Always include `source`** so the conclusion can be independently verified. Common fields: `result`, `narrative`, `source`, `evidence_summary`, `actual_vs_predicted`, `effect_size`.

**Time-bound vs. evidence-bound hypotheses:**

Not every hypothesis needs a deadline. A debugging hypothesis ("the leak is in the connection pool") resolves when the evidence is decisive — no calendar date needed. A prediction ("Bitcoin stays above $75k through March 4") has an explicit time window.

- **Has `deadline`?** The prediction window is still open until then. Current evidence may look decisive, but ask "could this still reverse?" If yes, stay in `testing` — add evidence, adjust confidence, and wait. When the deadline arrives, conclude.
- **No `deadline`?** Conclude when the evidence is decisive per your `falsification_criteria`. No need to wait for an arbitrary date.

Premature conclusions are permanent and cannot be undone (you'd have to `/revise`).

---

## Guidelines

- **Always set `created_by`** — traces which agent did what
- **Always set `falsification_criteria`** — if you can't disprove it, it's not testable
- **Decompose by default** — broad hypotheses → specific testable sub-hypotheses
- **Create competitors** — your first explanation is a cached pattern
- **Record ALL evidence** — never skip contradicting evidence
- **Zero contradicting evidence is a red flag** — you didn't look
- **Respond to propagated events** — `child_*`, `competing_*`, `dependency_*` signals need action
- **Use `revise` when the core claim changes** — preserves history via `parent_id`
- **Define channels before using them** — `POST /channels` with a goal so other agents know the mission
- **Set `channel` to organize by domain** — auto-normalized lowercase
- **Load channel goal + insights at session start** — the goal frames what the insights mean
- **Record insights relative to the channel goal** — "overconfident on timing" means nothing without context; "overconfident on earnings timing predictions" is actionable
- **Graduated formality** — formal fields (`null_hypothesis`, `experimental_design`, `significance_level`) are optional. Quick debugging? Skip them. Rigorous research? Use them all. Note: `outcome` is **required** when concluding.

---

## Common Mistakes

| Mistake | What happens | What to do instead |
|---------|--------------|--------------------|
| Concluding a time-bound hypothesis early | If it has a `deadline`, the prediction window is still open — you lock in a premature answer that can't be undone. | Stay in `testing`. Add evidence, adjust confidence, wait for the deadline to arrive. |
| Concluding without `outcome` | API rejects the transition with 422. You must explain the result. | Include an `outcome` object in the PATCH request with at least a `result`, `narrative`, and `source`. |
| No contradicting evidence | You were confirming, not testing. The system can't flag evidence you never looked for. | Actively search for disconfirming evidence. Record it even if weak. |
| Confidence only goes up | Classic confirmation bias. If confidence never dropped, you ignored counter-evidence. | Contradicting evidence should hurt more than supporting evidence helps. |
| Ignoring propagated events | Related hypotheses changed but you didn't update yours. Stale conclusions. | Process inbox regularly. `child_*`, `competing_*`, `dependency_*` events need action. |
| Trying to revert a terminal state | `supported`, `refuted`, `inconclusive`, `revised` are permanent. API rejects the transition. | Use `/revise` to create a corrected hypothesis. The original stays as a record. |
