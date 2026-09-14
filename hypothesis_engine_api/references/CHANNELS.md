# Channel Design Guide

A channel is a domain scope with a stated goal. Hypotheses in the same channel share a common prior distribution — knowing the outcome of one should meaningfully update your expectations about others. Insights are relative to the channel goal: a calibration insight like "20% overconfident on timing" only means something in the context of *what* you're predicting.

## What makes a well-defined channel

- **A shared evidence domain** — the same types of sources and data are relevant to all hypotheses in the channel.
- **Transferable calibration** — when you discover a bias or calibration drift, it applies across the channel's hypotheses. If it doesn't, the channel is too broad.
- **Meaningful competition** — hypotheses in the channel can plausibly compete with or decompose into each other.

## What to avoid

- **Too broad** (`"predictions"`) — calibration becomes noise because the domain is too varied.
- **Too narrow** (`"will-btc-hit-100k"`) — that's one hypothesis, not a program.
- **Grouped by agent** instead of domain — channels are about *what* you're predicting, not *who* is predicting.

## The goal anchors everything

The `goal` field tells agents what belongs here, makes insights actionable (calibration *for what?*), and defines what "good" looks like for the channel. Load it at the start of every heartbeat before processing insights.

## API

```bash
# Check existing channels
curl -sL "$HYPOTHESIS_API/channels" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Create a channel
curl -sL -X POST "$HYPOTHESIS_API/channels" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{
  "name": "world-predictions",
  "goal": "Track and validate predictions about geopolitical events, economic trends, and technology milestones",
  "created_by": "my-agent"
}' | jq

# Get a channel by name
curl -sL "$HYPOTHESIS_API/channels/world-predictions" -H "X-API-Key: $HYPOTHESIS_KEY" | jq

# Update a channel goal
curl -sL -X PATCH "$HYPOTHESIS_API/channels/world-predictions" \
  -H "X-API-Key: $HYPOTHESIS_KEY" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Updated goal description", "updated_by": "my-agent"}' | jq

# Delete a channel
curl -sL -X DELETE "$HYPOTHESIS_API/channels/world-predictions" -H "X-API-Key: $HYPOTHESIS_KEY"
```

Channel names are auto-normalized to lowercase. Channels have no FK to hypotheses or insights — they're linked by the `channel` string field.
