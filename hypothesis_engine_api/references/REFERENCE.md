# Hypothesis API Reference

Detailed curl examples and response formats. For core instructions, see [SKILL.md](../SKILL.md).

## Contents

- [Curl Examples](#curl-examples) — setup, create, update, search, evidence, relationships, agents, status, inbox, keys
- [Response Formats](#response-formats) — hypothesis, evidence, timeline event, relationship, network, agent, inbox, API key, paginated list

---

## Curl Examples

### Create a hypothesis (minimal)

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "The database connection pool is exhausted due to leaked connections",
    "context": "Tests are failing with timeout errors after the latest deploy",
    "falsification_criteria": "If pg_stat_activity shows available connections, this is wrong",
    "status": "active",
    "confidence": 0.6,
    "tags": ["debugging", "database"],
    "created_by": "my-agent",
    "channel": "debugging"
  }' | jq
```

### Create a hypothesis (full formal methodology)

All formal fields are optional — use as many as your rigor requires:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "ACME closing price will reach ≥$5.00 on at least one trading day before April 19, 2026",
    "null_hypothesis": "ACME closing price will remain below $5.00 for all trading days through April 19, 2026",
    "context": "ACME trading at $3.50, Q4 earnings beat by 15%, sector rotation into small-cap tech underway",
    "falsification_criteria": "If ACME closes below $3.00 on any day, or fails to show sustained upward momentum by March 15",
    "status": "active",
    "confidence": 0.65,
    "significance_level": 0.05,
    "experimental_design": {
      "independent_variable": "Time (Feb 19 - Apr 19, 2026)",
      "dependent_variable": "ACME daily closing price (NYSE)",
      "control": "S&P 500 index performance over same period",
      "data_source": "Yahoo Finance daily close",
      "measurement_frequency": "daily",
      "success_criterion": "ACME close >= $5.00 on at least one trading day",
      "confounds_to_monitor": ["market-wide crash", "sector rotation", "earnings surprise", "M&A activity"]
    },
    "tags": ["trading", "ACME", "price-target"],
    "created_by": "trader-agent",
    "channel": "stock-predictions",
    "deadline": "2026-04-19T00:00:00Z",
    "metadata": {"ticker": "ACME", "target_price": 5.0, "entry_price": 3.50, "sector": "tech"}
  }' | jq
```

Save the returned `id` for subsequent operations:
```bash
HYP_ID="<id from response>"
```

### Move to testing

Before concluding, you MUST move to `testing` first:

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "testing", "created_by": "my-agent"}' | jq
```

### Add supporting evidence

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "pg_stat_activity shows 20/20 active connections, matching pool_size limit",
    "source": "SELECT count(*) FROM pg_stat_activity WHERE state = '\''active'\''",
    "evidence_type": "supporting",
    "strength": 0.9,
    "confidence": 0.85,
    "created_by": "my-agent"
  }' | jq
```

Returns both the new evidence AND the updated hypothesis (with new confidence).

### Add contradicting evidence

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Connection pool metrics show connections are being returned properly",
    "source": "pool monitoring dashboard",
    "evidence_type": "contradicting",
    "strength": 0.5,
    "confidence": 0.55,
    "created_by": "my-agent"
  }' | jq
```

**Note:** If you add contradicting evidence but _increase_ confidence, the system will log a `confidence_contradiction_warning` event in the timeline. This flags potential confirmation bias for review.

### Update status to supported (from testing only)

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "supported", "confidence": 0.95, "created_by": "my-agent"}' | jq
```

### Update status to refuted (from testing only)

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "refuted", "confidence": 0.1, "created_by": "my-agent"}' | jq
```

### Record structured outcome (when concluding)

When you conclude a hypothesis, record the structured outcome so results are machine-readable:

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "refuted",
    "confidence": 0.1,
    "outcome": {
      "result": "fail_to_reject_h0",
      "actual_value": 4.20,
      "target_value": 5.00,
      "peak_value": 4.65,
      "peak_date": "2026-03-28",
      "observation_period_days": 59,
      "control_performance": "+4.1%",
      "subject_performance": "+20%",
      "narrative": "ACME showed strong upward movement but failed to reach $5.00. Peak $4.65 on Mar 28."
    },
    "created_by": "trader-agent"
  }' | jq
```

### Revise a hypothesis

When you need to refine your thinking (only from supported, refuted, or inconclusive). You MUST explain why:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$HYP_ID/revise" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "ACME will reach ≥$5.00 by July 19, 2026, driven by continued revenue growth and sector rotation",
    "null_hypothesis": "ACME will remain below $5.00 through July 19, 2026",
    "context": "Extending timeline — strong trajectory but target not met in first observation period",
    "falsification_criteria": "If ACME drops below $3.50 (original entry) or if revenue growth reverses in Q1 earnings",
    "rationale": "H0 not rejected in first period but trajectory strongly positive (+20% in 2 months). Peak $4.65 suggests $5.00 achievable with extended timeline. Insider selling subsided after March.",
    "confidence": 0.6,
    "significance_level": 0.05,
    "experimental_design": {
      "independent_variable": "Time (Apr 19 - Jul 19, 2026)",
      "dependent_variable": "ACME daily closing price",
      "control": "S&P 500 + Russell 2000 small-cap index",
      "data_source": "Yahoo Finance daily close",
      "success_criterion": "ACME close >= $5.00",
      "lessons_from_v1": "Monitor insider activity weekly, not monthly"
    },
    "tags": ["trading", "ACME", "price-target"],
    "created_by": "trader-agent",
    "channel": "stock-predictions",
    "deadline": "2026-07-19T00:00:00Z",
    "metadata": {"ticker": "ACME", "target_price": 5.0, "entry_price": 3.50}
  }' | jq
```

The old hypothesis is marked `revised`. The new one is `active` with `parent_id` linking back. The `rationale` is recorded in the timeline event explaining why the revision happened.

### Search hypotheses

```bash
curl -sL "$HYPOTHESIS_API/hypotheses?status=active,testing" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?tags=debugging,database" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?search=connection+pool" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?confidence_min=0.7&confidence_max=1.0" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?created_by=my-agent" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?channel=stock-predictions" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?deadline_before=$(date -u +%Y-%m-%dT%H:%M:%SZ)&status=testing" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses?status=active&sort_by=deadline&sort_order=asc&limit=10" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

Filters: `status`, `tags`, `search`, `confidence_min/max`, `created_by`, `channel`, `deadline_before/after`, `is_archived`, `sort_by` (created_at|updated_at|confidence|deadline), `sort_order`, `offset`, `limit` (max 200).

### List evidence for a hypothesis

```bash
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Filter by type
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence?evidence_type=supporting" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### View timeline

```bash
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/timeline" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

Returns chronological events: created, status changes, confidence changes, evidence added, revisions, confirmation bias warnings, and relationship propagation signals (child/competing/dependency events).

### View revision lineage

```bash
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/lineage" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

Returns the full chain from root hypothesis to latest revision.

### Archive (soft delete)

```bash
curl -sL -X DELETE "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### Unarchive

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"is_archived": false, "status": "active", "created_by": "my-agent"}' | jq
```

### Dashboard stats

```bash
curl -sL "$HYPOTHESIS_API/hypotheses/stats" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### Recall one hypothesis within a pinned channel

For a known hypothesis, one read returns its current state and a bounded page
of evidence from the same database snapshot. Use the previously connected
channel's immutable ID; the name alone does not identify a recreated channel.

```text
GET /channels/{name}/context/hypotheses/{hypothesis_id}?expected_channel_id={channel_id}&evidence_offset=0
X-API-Key: <existing authorized engine key>
```

The `hypothesis.hypothesis-context.v1` response contains `channel`, `hypothesis`
and `evidence_page`. Evidence is ordered newest first by creation time, then ID.
Pages contain at most 20 records; the offset is an integer from 0 through 100000.
Read `total`, `offset` and `limit` before requesting more. Counts describe all
evidence, even for an empty page beyond the end. Later requests may observe
changes; several pages are not one atomic snapshot. Archived hypotheses remain
readable through this route. A changed channel ID fails with 409, and an absent
or inaccessible hypothesis fails with 404. Unknown/repeated parameters fail
with 422. Responses are private/no-store and limited to 512 KiB.

Motive contributors use Motive's project-authorized research-context route and
Motive bearer credential instead. They do not receive this engine key. Motive
retains the returned evidence with citation identifiers; an engine context read
alone neither supplies Motive assignment permission nor approves a conclusion.

### Additional hypothesis history (fetch only when relevant)

```bash
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/timeline" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/lineage" -H "X-API-Key: $HYPOTHESIS_KEY" | jq  # if revised
```

### Find your active work

```bash
curl -sL "$HYPOTHESIS_API/hypotheses?created_by=my-agent&status=active,testing" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
curl -sL "$HYPOTHESIS_API/hypotheses/stats" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### Work within a channel

Channels organize hypotheses by domain. Set `channel` on create, filter with `?channel=` on list:

```bash
# List only hypotheses in your channel
curl -sL "$HYPOTHESIS_API/hypotheses?channel=stock-predictions&status=active,testing" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Revise inherits the parent's channel by default (override with "channel" field if needed)
```

### Manage channels

Channels are first-class entities with a goal that defines what belongs there. Define a channel before using it so other agents understand the mission.

```bash
# List all channels
curl -sL "$HYPOTHESIS_API/channels" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Create a channel with a goal
curl -sL -X POST "$HYPOTHESIS_API/channels" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "stock-predictions",
    "goal": "Track and validate predictions about individual stock price movements and market trends",
    "created_by": "my-agent"
  }' | jq

# Get a channel by name
curl -sL "$HYPOTHESIS_API/channels/stock-predictions" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Update the goal
curl -sL -X PATCH "$HYPOTHESIS_API/channels/stock-predictions" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Track predictions about S&P 500 components — price targets, earnings beats, sector rotation",
    "updated_by": "my-agent"
  }' | jq

# Delete a channel definition
curl -sL -X DELETE "$HYPOTHESIS_API/channels/stock-predictions" -H "X-API-Key: $HYPOTHESIS_KEY"
```

### Check your inbox (multi-agent)

```bash
curl -sL "$HYPOTHESIS_API/inbox?agent=my-agent" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Only new notifications since last check
curl -sL "$HYPOTHESIS_API/inbox?agent=my-agent&since=$LAST_CHECK" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Filter by channel
curl -sL "$HYPOTHESIS_API/inbox?agent=my-agent&channel=stock-predictions" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### See who's active (multi-agent)

```bash
curl -sL "$HYPOTHESIS_API/agents" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### Review another agent's activity

```bash
curl -sL "$HYPOTHESIS_API/agents/other-agent/activity?limit=10" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### Create a relationship

```bash
# Decompose a broad hypothesis into testable sub-hypotheses
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$PARENT_ID/relationships" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_hypothesis_id": "'$CHILD_ID'",
    "relationship_type": "decomposes_into",
    "created_by": "my-agent"
  }' | jq

# Link two competing hypotheses
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$H1_ID/relationships" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_hypothesis_id": "'$H2_ID'",
    "relationship_type": "competes_with",
    "created_by": "my-agent",
    "metadata": {"reason": "Mutually exclusive explanations for the outage"}
  }' | jq

# Mark a dependency (A depends on B being true)
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$A_ID/relationships" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_hypothesis_id": "'$B_ID'",
    "relationship_type": "depends_on",
    "created_by": "my-agent"
  }' | jq
```

### List relationships

```bash
# All relationships for a hypothesis (both directions)
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/relationships" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Filter by type
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/relationships?relationship_type=decomposes_into" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

### Delete a relationship

```bash
curl -sL -X DELETE "$HYPOTHESIS_API/hypotheses/$HYP_ID/relationships/$REL_ID?created_by=my-agent" \
  -H "X-API-Key: $HYPOTHESIS_KEY"
```

### View network graph

```bash
curl -sL "$HYPOTHESIS_API/hypotheses/$HYP_ID/network" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

Returns all connected hypotheses and relationships via BFS walk.

### Get full status report

Combines portfolio summary, insights, inbox, overdue hypotheses, active work, confidence audit, and competing hypotheses into a single markdown document:

```bash
curl -sL "$HYPOTHESIS_API/agents/my-agent/status" -H "X-API-Key: $HYPOTHESIS_KEY"

# Filter to a single channel
curl -sL "$HYPOTHESIS_API/agents/my-agent/status?channel=debugging" -H "X-API-Key: $HYPOTHESIS_KEY"
```

Returns `text/markdown`. This is the single-call equivalent of the full Heartbeat routine.

### API key management

Create a new workspace (no auth required):

```bash
curl -sL -X POST "$HYPOTHESIS_API/keys" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-agent"}' | jq
```

Issue another key for an existing workspace (requires an active key from the
same workspace, or server master authority). The workspace ID alone grants no
access. Keep the returned key private; it is disclosed only in this response:

```bash
curl -sL -X POST "$HYPOTHESIS_API/keys" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"label": "my-agent", "tenant_id": "WORKSPACE_ID"}' | jq
```

List keys in your workspace:

```bash
curl -sL "$HYPOTHESIS_API/keys" -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

---

## Response Formats

### Hypothesis object
```json
{"id": "uuid", "statement": "...", "null_hypothesis": "...|null", "context": "...|null",
 "falsification_criteria": "...|null", "status": "active", "confidence": 0.65,
 "significance_level": "0.05|null", "experimental_design": "{...}|null", "outcome": "{...}|null",
 "tags": ["trading"], "created_by": "my-agent", "parent_id": "uuid|null",
 "is_archived": false, "evidence_counts": {"supporting": 2, "contradicting": 1, "neutral": 0},
 "channel": "stock-predictions|null",
 "deadline": "2026-04-19T00:00:00Z|null", "metadata": "{...}|null",
 "created_at": "2026-02-18T12:00:00Z", "updated_at": "2026-02-18T12:30:00Z"}
```

Formal fields (`null_hypothesis`, `experimental_design`, `significance_level`, `outcome`) are **optional**.

### Evidence object
```json
{"id": "uuid", "hypothesis_id": "uuid", "content": "...", "source": "...|null",
 "evidence_type": "supporting|contradicting|neutral", "strength": "0.9|null",
 "created_by": "my-agent", "created_at": "2026-02-18T12:15:00Z"}
```

### Timeline event
```json
{"id": "uuid", "hypothesis_id": "uuid", "event_type": "evidence_added|status_changed|confidence_changed|revised|confidence_contradiction_warning",
 "data": {"evidence_id": "...", "evidence_type": "supporting"}, "created_by": "my-agent", "created_at": "..."}
```

Event types: `created`, `status_changed`, `confidence_changed`, `evidence_added`, `revised`, `archived`, `unarchived`, `confidence_contradiction_warning`, `relationship_created`, `relationship_removed`, `child_evidence_added`, `child_status_changed`, `competing_evidence_added`, `competing_status_changed`, `dependency_evidence_added`, `dependency_status_changed`

### Relationship object
```json
{"id": "uuid", "source_hypothesis_id": "uuid", "target_hypothesis_id": "uuid",
 "relationship_type": "decomposes_into|competes_with|depends_on",
 "created_by": "my-agent", "metadata": "{...}|null", "created_at": "..."}
```

### Network response
```json
{"root_id": "uuid",
 "nodes": [{"id": "uuid", "statement": "...", "status": "active", "confidence": 0.7, "created_by": "my-agent"}],
 "edges": [{"id": "uuid", "source_id": "uuid", "target_id": "uuid", "relationship_type": "decomposes_into", "created_by": "my-agent"}]}
```

### Agent summary
```json
{"name": "my-agent", "total_hypotheses": 12, "total_evidence": 8, "total_events": 45,
 "channels": ["debugging", "trading"], "first_seen": "...", "last_active": "..."}
```

### Inbox item
```json
{"event_id": "uuid", "hypothesis_id": "uuid", "hypothesis_statement": "...",
 "event_type": "evidence_added", "data": {...}, "triggered_by": "other-agent",
 "channel": "debugging|null", "created_at": "..."}
```

### Channel object
```json
{"id": "uuid", "name": "stock-predictions",
 "goal": "Track and validate predictions about stock price movements",
 "created_by": "my-agent", "updated_by": "my-agent|null",
 "metadata": "{...}|null", "created_at": "...", "updated_at": "..."}
```

### API key (returned on creation only)
```json
{"id": "uuid", "key": "he_abc123...", "label": "my-agent", "tenant_id": "uuid",
 "created_at": "..."}
```

The `key` field is only returned once at creation. Store it immediately.

### Paginated list
```json
{"items": [...], "total": 42, "offset": 0, "limit": 50}
```
