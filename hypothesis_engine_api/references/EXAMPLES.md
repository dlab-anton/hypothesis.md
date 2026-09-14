# Examples — Worked Workflows

Back to core instructions: [SKILL.md](../SKILL.md). Curl syntax and response formats: [REFERENCE.md](REFERENCE.md).

## Contents

- [Quick Track: Debugging](#quick-track-debugging) — minimal fields, fast cycle, 6 API calls
- [Full Formal: Price Prediction](#full-formal-price-prediction) — every feature, full methodology, multi-week cycle

---

## Quick Track: Debugging

**Situation:** Tests started failing after a deploy. You need to figure out why.

**Fields used:** `statement`, `context`, `falsification_criteria`, `confidence`, `created_by`. Nothing else.

### Step 1 — Predict before investigating

> "I think the Redis connection pool is exhausted because the new feature leaks connections."

State what you expect BEFORE looking at logs. This is what separates hypothesis-driven debugging from scrolling through output hoping something jumps out.

### Step 2 — Create hypothesis

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "Redis connection pool is exhausted because the new feature leaks connections",
    "context": "Tests failing with timeout errors after deploy of feature-xyz",
    "falsification_criteria": "If Redis shows available connections in the pool, this is wrong",
    "status": "active",
    "confidence": 0.5,
    "created_by": "debug-agent"
  }' | jq '.id'
```

No `null_hypothesis`, no `experimental_design`, no `deadline`, no `channel`, no `tags`, no `metadata`. Just the claim, why you think it, and what would prove you wrong.

```bash
HYP_ID="<returned id>"
```

### Step 3 — Move to testing

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "testing", "created_by": "debug-agent"}' | jq
```

### Step 4 — Seek disconfirming evidence first

Check Redis. Pool is full — 20/20 connections active. That supports the "exhausted" part. But the hypothesis claims *leaks*, so look for evidence against that mechanism:

```bash
# Supporting: pool IS exhausted
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Redis INFO shows 20/20 active connections, pool fully saturated",
    "source": "redis-cli INFO clients",
    "evidence_type": "supporting",
    "strength": 0.8,
    "confidence": 0.65,
    "created_by": "debug-agent"
  }' | jq
```

```bash
# Contradicting: connections are NOT leaking
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$HYP_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "Connection lifetimes are normal (avg 2s). Pool exhausted from high concurrency, not leaks.",
    "source": "redis-cli CLIENT LIST analysis",
    "evidence_type": "contradicting",
    "strength": 0.7,
    "confidence": 0.35,
    "created_by": "debug-agent"
  }' | jq
```

Pool IS exhausted (supporting), but NOT from leaks (contradicting the mechanism). Confidence dropped 0.65 → 0.35.

### Step 5 — Conclude

The statement claimed leaks. Evidence says no leaks. The right call is `inconclusive` — partially right (pool exhausted), mechanism wrong (not leaks):

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$HYP_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"status": "inconclusive", "confidence": 0.2, "created_by": "debug-agent"}' | jq
```

### Step 6 — Revise with what you learned

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$HYP_ID/revise" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "Redis pool is exhausted from increased concurrency in feature-xyz, not connection leaks",
    "context": "Pool is full but connections cycle normally. Feature-xyz makes 3x more Redis calls per request.",
    "falsification_criteria": "If disabling feature-xyz does not reduce connection count, concurrency is not the cause",
    "rationale": "Original hypothesis correctly identified pool exhaustion but wrong mechanism. CLIENT LIST shows normal connection lifetimes, ruling out leaks. Feature-xyz code review reveals 3 Redis calls per request vs 1 previously.",
    "confidence": 0.6,
    "created_by": "debug-agent"
  }' | jq
```

**Total: 6 API calls. No formal fields. The revised hypothesis carries forward everything learned from the first attempt via `parent_id` lineage.**

---

## Full Formal: Price Prediction

**Situation:** You're tracking whether ACME stock will hit $5.00 by a specific date. Full scientific methodology — null hypothesis, experimental design, significance level, competitors, structured outcome, insights.

**Fields used:** Everything.

### Step 1 — Load domain knowledge

```bash
curl -sL "$HYPOTHESIS_API/insights?channel=stock-predictions" \
  -H "X-API-Key: $HYPOTHESIS_KEY" | jq
```

Existing insight from a previous cycle:

```json
{"insight_type": "calibration", "content": "Timing predictions overconfident by ~20%. 4 of 6 missed by >2 weeks."}
```

This means: start confidence lower than your gut says. You would have picked 0.65, so start at 0.55.

### Step 2 — Create hypothesis (all fields)

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "ACME closing price will reach $5.00+ on at least one trading day before April 19, 2026",
    "null_hypothesis": "ACME closing price will remain below $5.00 through April 19, 2026",
    "context": "ACME at $3.50, Q4 earnings beat by 15%, sector rotation into small-cap tech",
    "falsification_criteria": "ACME closes below $3.00 on any day, or no upward momentum by March 15",
    "status": "active",
    "confidence": 0.55,
    "significance_level": 0.05,
    "experimental_design": {
      "independent_variable": "Time (Feb 19 - Apr 19, 2026)",
      "dependent_variable": "ACME daily closing price",
      "control": "S&P 500 performance over same period",
      "data_source": "Yahoo Finance daily close",
      "measurement_frequency": "daily",
      "success_criterion": "ACME close >= $5.00 on at least one trading day",
      "confounds_to_monitor": ["market-wide crash", "sector rotation reversal", "earnings surprise"]
    },
    "tags": ["trading", "acme", "price-target"],
    "created_by": "trader-agent",
    "channel": "stock-predictions",
    "deadline": "2026-04-19T00:00:00Z",
    "metadata": {"ticker": "ACME", "target_price": 5.0, "entry_price": 3.50}
  }' | jq '.id'
```

```bash
ACME_ID="<returned id>"
```

### Step 3 — Create a competing hypothesis

Your first theory is a cached pattern. Force yourself to consider alternatives:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "statement": "ACME will plateau between $3.50-$4.50 through April 19 as small-cap rotation stalls",
    "null_hypothesis": "ACME will break out of the $3.50-$4.50 range before April 19",
    "context": "Same macro conditions, but small-cap rallies historically lose steam in Q2",
    "falsification_criteria": "ACME closes above $4.50 for 3 consecutive days",
    "status": "active",
    "confidence": 0.4,
    "tags": ["trading", "acme", "price-target"],
    "created_by": "trader-agent",
    "channel": "stock-predictions",
    "deadline": "2026-04-19T00:00:00Z"
  }' | jq '.id'
```

```bash
ALT_ID="<returned id>"
```

Link them as competitors:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ACME_ID/relationships" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "target_hypothesis_id": "'$ALT_ID'",
    "relationship_type": "competes_with",
    "created_by": "trader-agent",
    "metadata": {"reason": "Mutually exclusive price predictions for same timeframe"}
  }' | jq
```

### Step 4 — Move to testing, gather evidence over weeks

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$ACME_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{"status": "testing", "created_by": "trader-agent"}' | jq

curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$ALT_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{"status": "testing", "created_by": "trader-agent"}' | jq
```

**Week 1** — ACME closes at $3.80 (+8.5%). Supporting:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ACME_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "content": "ACME closed at $3.80, up 8.5% in week 1. S&P up 1.2%. Outperforming control.",
    "source": "Yahoo Finance weekly close 2026-02-28",
    "evidence_type": "supporting",
    "strength": 0.5,
    "confidence": 0.6,
    "created_by": "trader-agent"
  }' | jq
```

**Week 3** — insider selling detected. Contradicting:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ACME_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "content": "SEC Form 4: CFO sold 50k shares at $4.10. Insider selling at these levels is bearish.",
    "source": "SEC EDGAR Form 4 filing 2026-03-14",
    "evidence_type": "contradicting",
    "strength": 0.6,
    "confidence": 0.5,
    "created_by": "trader-agent"
  }' | jq
```

Confidence dropped from 0.6 → 0.5 after contradicting evidence. This is correct — contradicting evidence should hurt more than supporting evidence helps.

**Week 6** — ACME peaked at $4.65 then pulled back. Neutral:

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ACME_ID/evidence" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "content": "ACME peaked at $4.65 on Mar 28, now at $4.20. Strong move but short of $5.00 target.",
    "source": "Yahoo Finance daily close 2026-03-31",
    "evidence_type": "neutral",
    "strength": 0.5,
    "confidence": 0.45,
    "created_by": "trader-agent"
  }' | jq
```

### Step 5 — Deadline arrives, conclude with structured outcome

Bullish thesis: refuted. ACME never hit $5.00.

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$ACME_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "status": "refuted",
    "confidence": 0.15,
    "outcome": {
      "result": "fail_to_reject_h0",
      "actual_value": 4.20,
      "target_value": 5.00,
      "peak_value": 4.65,
      "peak_date": "2026-03-28",
      "observation_period_days": 59,
      "control_performance": "+4.1%",
      "subject_performance": "+20%",
      "narrative": "Strong upward movement but failed to reach $5.00. Peak $4.65 on Mar 28. H0 not rejected."
    },
    "created_by": "trader-agent"
  }' | jq
```

Competitor (plateau thesis): also refuted. ACME did break $4.50 briefly.

```bash
curl -sL -X PATCH "$HYPOTHESIS_API/hypotheses/$ALT_ID" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "status": "refuted",
    "confidence": 0.2,
    "outcome": {
      "result": "rejected",
      "narrative": "ACME exceeded $4.50 range briefly (peak $4.65). Plateau thesis falsified, but bullish thesis also missed. Reality was between the two predictions."
    },
    "created_by": "trader-agent"
  }' | jq
```

Neither competitor won cleanly. Both refuted — that's a valid outcome and a learning opportunity.

### Step 6 — Revise with lessons learned

```bash
curl -sL -X POST "$HYPOTHESIS_API/hypotheses/$ACME_ID/revise" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "statement": "ACME will reach $5.00 by July 19, 2026, driven by continued revenue growth",
    "null_hypothesis": "ACME will remain below $5.00 through July 19, 2026",
    "context": "Extending timeline. +20% in 2 months but $5.00 not reached. Insider selling subsided after March.",
    "falsification_criteria": "ACME drops below $3.50 (original entry) or revenue growth reverses in Q1 earnings",
    "rationale": "H0 not rejected but trajectory strongly positive. Peak $4.65 suggests $5.00 achievable with extended timeline. Applying calibration insight: timing predictions are ~20% overconfident.",
    "confidence": 0.5,
    "significance_level": 0.05,
    "experimental_design": {
      "independent_variable": "Time (Apr 19 - Jul 19, 2026)",
      "dependent_variable": "ACME daily closing price",
      "control": "S&P 500 + Russell 2000",
      "data_source": "Yahoo Finance daily close",
      "success_criterion": "ACME close >= $5.00",
      "lessons_from_v1": "Monitor insider activity weekly. Apply 20% timing discount to momentum predictions."
    },
    "tags": ["trading", "acme", "price-target"],
    "created_by": "trader-agent",
    "channel": "stock-predictions",
    "deadline": "2026-07-19T00:00:00Z",
    "metadata": {"ticker": "ACME", "target_price": 5.0, "entry_price": 3.50, "revision": 2}
  }' | jq
```

The revised hypothesis starts fresh at `active` with `parent_id` linking back to the original. Full lineage preserved via `GET /hypotheses/$ACME_ID/lineage`.

### Step 7 — Record insight for future cycles

```bash
curl -sL -X POST "$HYPOTHESIS_API/insights" \
  -H "X-API-Key: $HYPOTHESIS_KEY" -H "Content-Type: application/json" \
  -d '{
    "channel": "stock-predictions",
    "insight_type": "calibration",
    "content": "Momentum-based price targets tend to overshoot on timing. ACME reached 93% of target ($4.65/$5.00) but missed deadline by >3 weeks. For momentum predictions, extend deadlines by 50%.",
    "created_by": "trader-agent",
    "metadata": {"sample_size": 1, "target_hit_rate": 0.0, "avg_target_proximity": 0.93}
  }' | jq
```

This insight persists across sessions. Next time any agent in this channel creates a momentum-based price prediction, loading insights at session start surfaces this calibration data automatically.

**Total: ~15 API calls across weeks. Every field used. Full audit trail. Insight feeds future predictions.**

### Key differences from quick track

| | Quick track | Full formal |
|---|---|---|
| Fields used | 5 | 15+ |
| API calls | 6 | ~15 |
| Duration | Minutes | Weeks |
| Relationships | None | `competes_with` |
| Insights | None | Loaded + recorded |
| Outcome | Implicit (status) | Structured (machine-readable) |
| Formal methodology | Skipped | `null_hypothesis`, `experimental_design`, `significance_level` |

Both workflows follow The Loop. The formal version just fills in more structure at each step. Start quick, add formality when the stakes justify it.
