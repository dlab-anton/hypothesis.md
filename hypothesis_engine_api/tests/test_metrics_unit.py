"""Unit tests for metrics computation — no database required.

Tests the pure computation functions in metrics_service.py using mock data objects.
"""

import math
import uuid
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

import pytest

from app.services.metrics_service import (
    compute_brier,
    compute_calibration,
    compute_prediction_value,
    compute_falsification,
    compute_confidence_dynamics,
    compute_learning_rate,
    get_initial_confidences,
    ROLLING_WINDOW,
)


def _hyp(
    status="supported",
    confidence=0.8,
    initial_confidence=None,
    falsification_criteria=None,
    deadline=None,
    parent_id=None,
    updated_at=None,
):
    """Create a mock hypothesis."""
    return SimpleNamespace(
        id=uuid.uuid4(),
        status=status,
        confidence=confidence,
        initial_confidence=initial_confidence,
        falsification_criteria=falsification_criteria,
        deadline=deadline,
        parent_id=parent_id,
        created_at=datetime.now(timezone.utc),
        updated_at=updated_at or datetime.now(timezone.utc),
    )


def _evidence(hypothesis_id, evidence_type="supporting", confidence_after=None):
    return SimpleNamespace(
        id=uuid.uuid4(),
        hypothesis_id=hypothesis_id,
        evidence_type=evidence_type,
        confidence_after=confidence_after,
        created_at=datetime.now(timezone.utc),
    )


def _event(hypothesis_id, old_confidence, new_confidence):
    return SimpleNamespace(
        id=uuid.uuid4(),
        hypothesis_id=hypothesis_id,
        event_type="confidence_changed",
        data={"old_confidence": old_confidence, "new_confidence": new_confidence},
        created_at=datetime.now(timezone.utc),
    )


# ── Brier Score ──────────────────────────────────────────────────────


class TestBrierScore:
    def test_empty(self):
        result = compute_brier([])
        assert result.score is None
        assert result.rating == "insufficient_data"
        assert result.sample_size == 0

    def test_perfect_predictions(self):
        """Supported at 1.0 and refuted at 0.0 → Brier = 0."""
        h1 = _hyp(status="supported", confidence=0.999)
        h2 = _hyp(status="refuted", confidence=0.001)
        result = compute_brier([h1, h2])
        assert result.score is not None
        assert result.score < 0.001
        assert result.rating == "excellent"

    def test_coin_flip(self):
        """Everything at 0.5 → Brier = 0.25."""
        hyps = [_hyp(status="supported", confidence=0.5) for _ in range(10)]
        hyps += [_hyp(status="refuted", confidence=0.5) for _ in range(10)]
        result = compute_brier(hyps)
        assert result.score == pytest.approx(0.25, abs=0.001)
        assert result.rating == "poor"

    def test_known_values(self):
        """Three hypotheses with known Brier scores."""
        h1 = _hyp(status="supported", confidence=0.9)  # (0.9-1)^2 = 0.01
        h2 = _hyp(status="refuted", confidence=0.1)     # (0.1-0)^2 = 0.01
        h3 = _hyp(status="supported", confidence=0.5)   # (0.5-1)^2 = 0.25
        result = compute_brier([h1, h2, h3])
        expected = (0.01 + 0.01 + 0.25) / 3
        assert result.score == pytest.approx(expected, abs=0.001)
        assert result.sample_size == 3

    def test_rolling_window(self):
        """Rolling scores appear only after ROLLING_WINDOW predictions."""
        hyps = [_hyp(status="supported", confidence=0.8) for _ in range(25)]
        result = compute_brier(hyps)
        # 25 - 20 + 1 = 6 rolling scores
        assert len(result.rolling_scores) == 25 - ROLLING_WINDOW + 1

    def test_no_rolling_under_window(self):
        hyps = [_hyp(status="supported", confidence=0.8) for _ in range(5)]
        result = compute_brier(hyps)
        assert len(result.rolling_scores) == 0

    def test_rating_thresholds(self):
        # Excellent: score < 0.10
        h = _hyp(status="supported", confidence=0.95)  # (0.95-1)^2 = 0.0025
        assert compute_brier([h]).rating == "excellent"

        # Good: 0.10 <= score < 0.20
        h = _hyp(status="supported", confidence=0.6)  # (0.6-1)^2 = 0.16
        assert compute_brier([h]).rating == "good"

        # Fair: 0.20 <= score < 0.25
        h = _hyp(status="refuted", confidence=0.45)  # (0.45-0)^2 = 0.2025
        assert compute_brier([h]).rating == "fair"

        # Poor: score >= 0.25
        h = _hyp(status="supported", confidence=0.4)  # (0.4-1)^2 = 0.36
        assert compute_brier([h]).rating == "poor"


# ── Calibration ──────────────────────────────────────────────────────


class TestCalibration:
    def test_empty(self):
        result = compute_calibration([], {})
        assert result.calibration_error is None
        assert result.sample_size == 0
        assert len(result.buckets) == 5

    def test_perfect_calibration(self):
        """In 0.8-1.0 bucket (midpoint 0.9), 9 supported + 1 refuted = 0.9 hit rate."""
        hyps = [_hyp(status="supported", confidence=0.85) for _ in range(9)]
        hyps.append(_hyp(status="refuted", confidence=0.85))
        initials = {h.id: 0.85 for h in hyps}
        result = compute_calibration(hyps, initials)
        # Bucket [0.8, 1.0] midpoint 0.9, hit_rate 0.9 → error = 0
        bucket = result.buckets[4]
        assert bucket.count == 10
        assert bucket.hit_rate == pytest.approx(0.9, abs=0.001)
        assert result.calibration_error == pytest.approx(0.0, abs=0.001)

    def test_overconfident(self):
        """All at 0.9 confidence but only 50% supported → overconfident."""
        hyps = [_hyp(status="supported", confidence=0.9) for _ in range(5)]
        hyps += [_hyp(status="refuted", confidence=0.9) for _ in range(5)]
        initials = {h.id: 0.9 for h in hyps}
        result = compute_calibration(hyps, initials)
        bucket = result.buckets[4]  # 0.8-1.0
        assert bucket.hit_rate == pytest.approx(0.5, abs=0.001)
        # Error = |0.9 - 0.5| = 0.4
        assert result.calibration_error == pytest.approx(0.4, abs=0.001)

    def test_multiple_buckets(self):
        hyps = [
            _hyp(status="supported", confidence=0.1),   # bucket 0.0-0.2
            _hyp(status="supported", confidence=0.9),   # bucket 0.8-1.0
        ]
        initials = {hyps[0].id: 0.1, hyps[1].id: 0.9}
        result = compute_calibration(hyps, initials)
        assert result.buckets[0].count == 1
        assert result.buckets[0].hit_rate == 1.0
        assert result.buckets[4].count == 1
        assert result.buckets[4].hit_rate == 1.0


# ── Prediction Value ─────────────────────────────────────────────────


class TestPredictionValue:
    def test_empty(self):
        result = compute_prediction_value([], {})
        assert result.mean_bits is None
        assert result.sample_size == 0

    def test_obvious_prediction(self):
        """Supported at 0.99 confidence → ~0.014 bits (low information)."""
        h = _hyp(status="supported", confidence=0.99)
        initials = {h.id: 0.99}
        result = compute_prediction_value([h], initials)
        expected = -math.log2(0.99)
        assert result.mean_bits == pytest.approx(expected, abs=0.001)
        assert result.mean_bits < 0.02

    def test_uncertain_correct(self):
        """Supported at 0.55 → ~0.86 bits (high information)."""
        h = _hyp(status="supported", confidence=0.55)
        initials = {h.id: 0.55}
        result = compute_prediction_value([h], initials)
        expected = -math.log2(0.55)
        assert result.mean_bits == pytest.approx(expected, abs=0.01)
        assert result.mean_bits > 0.8

    def test_refuted_prediction(self):
        """Refuted at 0.3 → -log2(1-0.3) = -log2(0.7) ≈ 0.515 bits."""
        h = _hyp(status="refuted", confidence=0.3)
        initials = {h.id: 0.3}
        result = compute_prediction_value([h], initials)
        expected = -math.log2(0.7)
        assert result.mean_bits == pytest.approx(expected, abs=0.01)

    def test_total_bits(self):
        h1 = _hyp(status="supported", confidence=0.9)
        h2 = _hyp(status="supported", confidence=0.5)
        initials = {h1.id: 0.9, h2.id: 0.5}
        result = compute_prediction_value([h1, h2], initials)
        expected_total = -math.log2(0.9) + -math.log2(0.5)
        assert result.total_bits == pytest.approx(expected_total, abs=0.01)


# ── Falsification Rigor ──────────────────────────────────────────────


class TestFalsification:
    def test_empty(self):
        result = compute_falsification([], {}, {})
        assert result.evidence_balance_ratio is None
        assert result.falsification_coverage is None
        assert result.confidence_reversal_rate is None

    def test_evidence_balance(self):
        h = _hyp()
        evidence = {
            h.id: [
                _evidence(h.id, "supporting"),
                _evidence(h.id, "supporting"),
                _evidence(h.id, "contradicting"),
                _evidence(h.id, "neutral"),
            ]
        }
        result = compute_falsification([h], evidence, {})
        # 1 contradicting / 4 total = 0.25
        assert result.evidence_balance_ratio == pytest.approx(0.25, abs=0.001)

    def test_falsification_coverage(self):
        h1 = _hyp(falsification_criteria="disprove by X")
        h2 = _hyp(falsification_criteria=None)
        h3 = _hyp(falsification_criteria="disprove by Y")
        result = compute_falsification([h1, h2, h3], {}, {})
        assert result.falsification_coverage == pytest.approx(2 / 3, abs=0.001)

    def test_confidence_reversal_rate(self):
        h1 = _hyp()
        h2 = _hyp()
        # h1: went up then down → reversal
        events = {
            h1.id: [
                _event(h1.id, 0.5, 0.7),
                _event(h1.id, 0.7, 0.4),
            ],
            # h2: only went up → no reversal
            h2.id: [
                _event(h2.id, 0.3, 0.5),
                _event(h2.id, 0.5, 0.8),
            ],
        }
        result = compute_falsification([h1, h2], {}, events)
        assert result.confidence_reversal_rate == pytest.approx(0.5, abs=0.001)


# ── Confidence Dynamics ──────────────────────────────────────────────


class TestConfidenceDynamics:
    def test_empty(self):
        result = compute_confidence_dynamics([], {}, {}, [])
        assert result.mean_absolute_drift is None
        assert result.mean_update_magnitude is None

    def test_drift(self):
        h = _hyp(status="supported", confidence=0.9)
        initials = {h.id: 0.5}
        result = compute_confidence_dynamics([h], initials, {}, [h])
        assert result.mean_absolute_drift == pytest.approx(0.4, abs=0.001)

    def test_evidence_responsiveness(self):
        h = _hyp(status="supported", confidence=0.9)
        initials = {h.id: 0.5}
        now = datetime.now(timezone.utc)
        evidence = {
            h.id: [
                _evidence(h.id, "supporting", confidence_after=0.6),
                _evidence(h.id, "supporting", confidence_after=0.8),
            ]
        }
        # Fix created_at ordering
        evidence[h.id][0].created_at = now
        evidence[h.id][1].created_at = now + timedelta(seconds=1)

        result = compute_confidence_dynamics([h], initials, evidence, [h])
        # Deltas: |0.6 - 0.5| = 0.1, |0.8 - 0.6| = 0.2 → mean = 0.15
        assert result.mean_update_magnitude == pytest.approx(0.15, abs=0.001)

    def test_premature_conclusion(self):
        """Hypothesis concluded before deadline and later revised."""
        future = datetime.now(timezone.utc) + timedelta(days=30)
        h_parent = _hyp(
            status="supported",
            confidence=0.9,
            deadline=future,
            updated_at=datetime.now(timezone.utc),
        )
        h_child = _hyp(status="active", parent_id=h_parent.id)

        result = compute_confidence_dynamics(
            [h_parent], {h_parent.id: 0.5}, {}, [h_parent, h_child]
        )
        assert result.premature_conclusion_rate == pytest.approx(1.0, abs=0.001)


# ── Learning Rate ────────────────────────────────────────────────────


class TestLearningRate:
    def test_insufficient_data(self):
        result = compute_learning_rate([], 5, 0)
        assert result.slope is None
        assert result.interpretation == "insufficient_data"

    def test_improving(self):
        """Decreasing Brier scores → negative slope."""
        rolling = [0.30, 0.25, 0.20, 0.15, 0.10]
        result = compute_learning_rate(rolling, 3, 25)
        assert result.slope is not None
        assert result.slope < -0.005
        assert result.interpretation == "improving"

    def test_declining(self):
        """Increasing Brier scores → positive slope."""
        rolling = [0.10, 0.15, 0.20, 0.25, 0.30]
        result = compute_learning_rate(rolling, 0, 25)
        assert result.slope is not None
        assert result.slope > 0.005
        assert result.interpretation == "declining"

    def test_stable(self):
        """Flat Brier scores → near-zero slope."""
        rolling = [0.20, 0.20, 0.20, 0.20, 0.20]
        result = compute_learning_rate(rolling, 2, 25)
        assert result.slope is not None
        assert abs(result.slope) < 0.005
        assert result.interpretation == "stable"


# ── Initial Confidence ───────────────────────────────────────────────


class TestInitialConfidences:
    def test_from_stored_initial_confidence(self):
        """initial_confidence field takes highest priority."""
        h = _hyp(confidence=0.9, initial_confidence=0.6)
        events = {h.id: [_event(h.id, 0.5, 0.7)]}
        result = get_initial_confidences([h], events)
        # Should use stored initial_confidence (0.6), NOT event (0.5) or current (0.9)
        assert result[h.id] == pytest.approx(0.6, abs=0.001)

    def test_from_event_when_no_initial_confidence(self):
        """Falls back to event reconstruction when initial_confidence is None."""
        h = _hyp(confidence=0.9)
        events = {h.id: [_event(h.id, 0.5, 0.7)]}
        result = get_initial_confidences([h], events)
        assert result[h.id] == pytest.approx(0.5, abs=0.001)

    def test_no_events_uses_current(self):
        h = _hyp(confidence=0.8)
        result = get_initial_confidences([h], {})
        assert result[h.id] == pytest.approx(0.8, abs=0.001)

    def test_null_confidence_fallback(self):
        h = _hyp(confidence=None)
        result = get_initial_confidences([h], {})
        assert result[h.id] == pytest.approx(0.5, abs=0.001)

    def test_initial_confidence_ignores_events(self):
        """When initial_confidence is set, events are not consulted."""
        h = _hyp(confidence=0.9, initial_confidence=0.3)
        events = {h.id: [_event(h.id, 0.7, 0.8)]}
        result = get_initial_confidences([h], events)
        assert result[h.id] == pytest.approx(0.3, abs=0.001)
