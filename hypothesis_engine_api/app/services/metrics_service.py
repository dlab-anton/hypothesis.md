"""Core prediction quality metrics computation.

Fetches hypothesis/evidence/event data via SQL, computes 6 metrics in Python.
All pure computation functions are module-level for easy unit testing.
"""

import math
import uuid
from collections import defaultdict
from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models.hypothesis import Hypothesis
from ..db.models.evidence import Evidence
from ..db.models.event import Event
from ..db.models.insight import Insight
from ..schemas.metrics import (
    MetricsResponse,
    BrierScoreMetrics,
    CalibrationBucket,
    CalibrationMetrics,
    PredictionValueMetrics,
    FalsificationRigorMetrics,
    ConfidenceDynamicsMetrics,
    LearningRateMetrics,
)


# ── Constants ────────────────────────────────────────────────────────

CONCLUDED_STATUSES = ("supported", "refuted")
ROLLING_WINDOW = 20
CONFIDENCE_BINS = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
CONFIDENCE_FALLBACK = 0.5  # maximum uncertainty


# ── Pure computation functions ───────────────────────────────────────


def _safe_conf(val: Optional[float]) -> float:
    """Clamp confidence to (0.001, 0.999) for log safety, default 0.5."""
    if val is None:
        return CONFIDENCE_FALLBACK
    return max(0.001, min(0.999, val))


def _mean(values: list[float]) -> Optional[float]:
    if not values:
        return None
    return sum(values) / len(values)


def get_initial_confidences(
    hypotheses: list[Any],
    events_by_hypothesis: dict[uuid.UUID, list[Any]],
) -> dict[uuid.UUID, float]:
    """Get initial confidence for each hypothesis.

    Priority:
    1. h.initial_confidence (set at creation, immutable — most reliable)
    2. First confidence_changed event's old_confidence (legacy reconstruction)
    3. Current confidence (no changes ever made)
    4. 0.5 fallback (maximum uncertainty)
    """
    result = {}
    for h in hypotheses:
        # Prefer the stored initial_confidence field
        stored = getattr(h, "initial_confidence", None)
        if stored is not None:
            result[h.id] = _safe_conf(stored)
            continue
        # Legacy fallback: reconstruct from events
        events = events_by_hypothesis.get(h.id, [])
        if events:
            old = events[0].data.get("old_confidence") if events[0].data else None
            result[h.id] = _safe_conf(old)
        else:
            result[h.id] = _safe_conf(h.confidence)
    return result


def compute_brier(
    concluded: list[Any],
) -> BrierScoreMetrics:
    """Brier score: mean((confidence - outcome)²)."""
    if not concluded:
        return BrierScoreMetrics(sample_size=0)

    # Sort by updated_at for rolling window (chronological order of conclusions)
    sorted_h = sorted(concluded, key=lambda h: h.updated_at)

    scores = []
    for h in sorted_h:
        outcome = 1.0 if h.status == "supported" else 0.0
        conf = _safe_conf(h.confidence)
        scores.append((conf - outcome) ** 2)

    overall = _mean(scores)

    # Rolling window
    rolling = []
    for i in range(ROLLING_WINDOW, len(scores) + 1):
        window = scores[i - ROLLING_WINDOW : i]
        rolling.append(round(sum(window) / len(window), 4))

    # Rating
    if overall is None:
        rating = "insufficient_data"
    elif overall < 0.10:
        rating = "excellent"
    elif overall < 0.20:
        rating = "good"
    elif overall < 0.25:
        rating = "fair"
    else:
        rating = "poor"

    return BrierScoreMetrics(
        score=round(overall, 4) if overall is not None else None,
        rating=rating,
        rolling_scores=rolling,
        sample_size=len(scores),
    )


def compute_calibration(
    concluded: list[Any],
    initial_confidences: dict[uuid.UUID, float],
) -> CalibrationMetrics:
    """Bucket hypotheses by confidence, compute hit rate per bucket."""
    buckets = []
    for start, end in CONFIDENCE_BINS:
        mid = round((start + end) / 2, 1)
        in_bucket = [
            h
            for h in concluded
            if start <= initial_confidences.get(h.id, CONFIDENCE_FALLBACK) < end
            or (end == 1.0 and initial_confidences.get(h.id, CONFIDENCE_FALLBACK) == 1.0)
        ]
        count = len(in_bucket)
        if count > 0:
            hits = sum(1 for h in in_bucket if h.status == "supported")
            hit_rate = round(hits / count, 4)
        else:
            hit_rate = None
        buckets.append(CalibrationBucket(
            bin_start=start, bin_end=end, midpoint=mid, count=count, hit_rate=hit_rate
        ))

    # Calibration error: mean |midpoint - hit_rate| over non-empty buckets
    errors = [abs(b.midpoint - b.hit_rate) for b in buckets if b.hit_rate is not None]
    cal_error = round(sum(errors) / len(errors), 4) if errors else None

    return CalibrationMetrics(
        buckets=buckets,
        calibration_error=cal_error,
        sample_size=len(concluded),
    )


def compute_prediction_value(
    concluded: list[Any],
    initial_confidences: dict[uuid.UUID, float],
) -> PredictionValueMetrics:
    """Information content: -log2(p) for correct predictions."""
    bits = []
    for h in concluded:
        conf = initial_confidences.get(h.id, CONFIDENCE_FALLBACK)
        conf = max(0.001, min(0.999, conf))
        if h.status == "supported":
            bits.append(-math.log2(conf))
        else:  # refuted
            bits.append(-math.log2(1 - conf))

    return PredictionValueMetrics(
        mean_bits=round(_mean(bits), 4) if bits else None,
        total_bits=round(sum(bits), 4) if bits else 0.0,
        sample_size=len(bits),
    )


def compute_falsification(
    all_hypotheses: list[Any],
    evidence_by_hypothesis: dict[uuid.UUID, list[Any]],
    events_by_hypothesis: dict[uuid.UUID, list[Any]],
) -> FalsificationRigorMetrics:
    """Evidence balance, falsification coverage, confidence reversal rate."""
    # (a) Evidence balance: contradicting / total
    total_s = total_c = total_n = 0
    for ev_list in evidence_by_hypothesis.values():
        for ev in ev_list:
            if ev.evidence_type == "contradicting":
                total_c += 1
            elif ev.evidence_type == "supporting":
                total_s += 1
            else:
                total_n += 1
    total_ev = total_s + total_c + total_n
    balance = round(total_c / total_ev, 4) if total_ev > 0 else None

    # (b) Falsification criteria coverage
    if all_hypotheses:
        with_criteria = sum(1 for h in all_hypotheses if h.falsification_criteria)
        coverage = round(with_criteria / len(all_hypotheses), 4)
    else:
        coverage = None

    # (c) Confidence reversal rate: bidirectional movement
    hypotheses_with_events = 0
    reversals = 0
    for h_id, events in events_by_hypothesis.items():
        if not events:
            continue
        hypotheses_with_events += 1
        went_up = went_down = False
        for ev in events:
            data = ev.data or {}
            old = data.get("old_confidence")
            new = data.get("new_confidence")
            if old is not None and new is not None:
                if new > old:
                    went_up = True
                if new < old:
                    went_down = True
        if went_up and went_down:
            reversals += 1
    reversal_rate = (
        round(reversals / hypotheses_with_events, 4) if hypotheses_with_events > 0 else None
    )

    return FalsificationRigorMetrics(
        evidence_balance_ratio=balance,
        falsification_coverage=coverage,
        confidence_reversal_rate=reversal_rate,
        sample_size=len(all_hypotheses),
    )


def compute_confidence_dynamics(
    concluded: list[Any],
    initial_confidences: dict[uuid.UUID, float],
    evidence_by_hypothesis: dict[uuid.UUID, list[Any]],
    all_hypotheses: list[Any],
) -> ConfidenceDynamicsMetrics:
    """Drift, evidence responsiveness, premature conclusion rate."""
    # (a) Mean absolute drift: |final - initial|
    drifts = []
    for h in concluded:
        initial = initial_confidences.get(h.id, CONFIDENCE_FALLBACK)
        final = _safe_conf(h.confidence)
        drifts.append(abs(final - initial))
    mean_drift = round(_mean(drifts), 4) if drifts else None

    # (b) Evidence responsiveness: mean |Δconfidence| per evidence
    deltas: list[float] = []
    for h in concluded:
        ev_list = evidence_by_hypothesis.get(h.id, [])
        sorted_ev = sorted(ev_list, key=lambda e: e.created_at)
        prev_conf = initial_confidences.get(h.id, CONFIDENCE_FALLBACK)
        for ev in sorted_ev:
            if ev.confidence_after is not None:
                deltas.append(abs(ev.confidence_after - prev_conf))
                prev_conf = ev.confidence_after
    mean_update = round(_mean(deltas), 4) if deltas else None

    # (c) Premature conclusion rate: concluded before deadline AND later revised
    # A hypothesis is "premature" if it concluded before its deadline and has a child
    # (i.e., another hypothesis has parent_id = this hypothesis's id)
    revised_parent_ids = {h.parent_id for h in all_hypotheses if h.parent_id is not None}
    premature = 0
    with_deadline = 0
    for h in concluded:
        if h.deadline is None:
            continue
        with_deadline += 1
        # Concluded before deadline and was later revised
        if h.updated_at <= h.deadline and h.id in revised_parent_ids:
            premature += 1
    premature_rate = round(premature / with_deadline, 4) if with_deadline > 0 else None

    return ConfidenceDynamicsMetrics(
        mean_absolute_drift=mean_drift,
        mean_update_magnitude=mean_update,
        premature_conclusion_rate=premature_rate,
        sample_size=len(concluded),
    )


def compute_learning_rate(
    rolling_brier: list[float],
    insight_count: int,
    sample_size: int,
) -> LearningRateMetrics:
    """Linear regression slope on rolling Brier scores."""
    if len(rolling_brier) < 3:
        return LearningRateMetrics(
            interpretation="insufficient_data",
            insight_count=insight_count,
            sample_size=sample_size,
        )

    n = len(rolling_brier)
    x_mean = (n - 1) / 2.0
    y_mean = sum(rolling_brier) / n

    numerator = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(rolling_brier))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    slope = numerator / denominator if denominator != 0 else 0.0

    if slope < -0.005:
        interpretation = "improving"
    elif slope > 0.005:
        interpretation = "declining"
    else:
        interpretation = "stable"

    return LearningRateMetrics(
        slope=round(slope, 6),
        interpretation=interpretation,
        insight_count=insight_count,
        sample_size=sample_size,
    )


# ── Main coordinator ─────────────────────────────────────────────────


async def get_metrics(
    db: AsyncSession,
    *,
    tenant_id: Optional[uuid.UUID] = None,
    channel: Optional[str] = None,
    created_by: Optional[str] = None,
) -> MetricsResponse:
    """Compute all 6 prediction quality metrics for a tenant."""

    # ── 1. Fetch all non-archived hypotheses ──
    base_filters = [Hypothesis.is_archived == False]  # noqa: E712
    if tenant_id is not None:
        base_filters.append(Hypothesis.tenant_id == tenant_id)
    if channel is not None:
        base_filters.append(Hypothesis.channel == channel.lower())
    if created_by is not None:
        base_filters.append(Hypothesis.created_by == created_by)

    all_query = select(Hypothesis).where(and_(*base_filters))
    all_result = await db.execute(all_query)
    all_hypotheses = list(all_result.scalars().all())

    # ── 2. Filter to concluded ──
    concluded = [h for h in all_hypotheses if h.status in CONCLUDED_STATUSES]
    concluded_ids = [h.id for h in concluded]

    if not all_hypotheses:
        return MetricsResponse()

    # ── 3. Batch-fetch evidence for all hypotheses (for falsification metrics) ──
    evidence_by_hypothesis: dict[uuid.UUID, list[Evidence]] = defaultdict(list)
    all_ids = [h.id for h in all_hypotheses]
    if all_ids:
        ev_result = await db.execute(
            select(Evidence)
            .where(Evidence.hypothesis_id.in_(all_ids))
            .order_by(Evidence.created_at.asc())
        )
        for ev in ev_result.scalars().all():
            evidence_by_hypothesis[ev.hypothesis_id].append(ev)

    # ── 4. Batch-fetch confidence_changed events for concluded hypotheses ──
    events_by_hypothesis: dict[uuid.UUID, list[Event]] = defaultdict(list)
    if concluded_ids:
        ev_result = await db.execute(
            select(Event)
            .where(
                and_(
                    Event.hypothesis_id.in_(concluded_ids),
                    Event.event_type == "confidence_changed",
                )
            )
            .order_by(Event.created_at.asc())
        )
        for ev in ev_result.scalars().all():
            events_by_hypothesis[ev.hypothesis_id].append(ev)

    # ── 5. Count insights ──
    insight_filters = []
    if tenant_id is not None:
        insight_filters.append(Insight.tenant_id == tenant_id)
    insight_query = select(func.count(Insight.id))
    if insight_filters:
        insight_query = insight_query.where(and_(*insight_filters))
    insight_result = await db.execute(insight_query)
    insight_count = insight_result.scalar_one()

    # ── 6. Compute initial confidences ──
    initial_confidences = get_initial_confidences(concluded, events_by_hypothesis)

    # ── 7. Compute all metrics ──
    brier = compute_brier(concluded)
    calibration = compute_calibration(concluded, initial_confidences)
    prediction_value = compute_prediction_value(concluded, initial_confidences)
    falsification = compute_falsification(all_hypotheses, evidence_by_hypothesis, events_by_hypothesis)
    dynamics = compute_confidence_dynamics(
        concluded, initial_confidences, evidence_by_hypothesis, all_hypotheses
    )
    learning = compute_learning_rate(brier.rolling_scores, insight_count, brier.sample_size)

    return MetricsResponse(
        brier=brier,
        calibration=calibration,
        prediction_value=prediction_value,
        falsification=falsification,
        confidence_dynamics=dynamics,
        learning_rate=learning,
        concluded_count=len(concluded),
        total_count=len(all_hypotheses),
    )
