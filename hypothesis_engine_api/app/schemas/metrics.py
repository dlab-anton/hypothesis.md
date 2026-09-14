from typing import Optional
from pydantic import BaseModel, Field


class BrierScoreMetrics(BaseModel):
    """Brier score: mean((confidence - outcome)²). 0 = perfect, 0.25 = coin flip."""

    score: Optional[float] = Field(None, description="Overall Brier score (0=perfect, 1=worst)")
    rating: str = Field(
        "insufficient_data",
        description="excellent (<0.10), good (<0.20), fair (<0.25), poor (>=0.25)",
    )
    rolling_scores: list[float] = Field(
        default_factory=list, description="Rolling 20-prediction Brier scores"
    )
    sample_size: int = Field(0, description="Number of concluded (supported/refuted) hypotheses")


class CalibrationBucket(BaseModel):
    bin_start: float
    bin_end: float
    midpoint: float
    count: int = 0
    hit_rate: Optional[float] = Field(None, description="Fraction supported in this bucket")


class CalibrationMetrics(BaseModel):
    """When you say 70%, does it happen 70% of the time?"""

    buckets: list[CalibrationBucket] = Field(default_factory=list)
    calibration_error: Optional[float] = Field(
        None, description="Mean |midpoint - hit_rate| across non-empty buckets"
    )
    sample_size: int = 0


class PredictionValueMetrics(BaseModel):
    """Information content: are you predicting hard things or easy things?"""

    mean_bits: Optional[float] = Field(None, description="Average bits per prediction")
    total_bits: float = Field(0.0, description="Total information bits produced")
    sample_size: int = 0


class FalsificationRigorMetrics(BaseModel):
    """Is the agent trying to disprove its hypotheses?"""

    evidence_balance_ratio: Optional[float] = Field(
        None, description="contradicting / total evidence (healthy: 0.2-0.4)"
    )
    falsification_coverage: Optional[float] = Field(
        None, description="Fraction of hypotheses with falsification criteria"
    )
    confidence_reversal_rate: Optional[float] = Field(
        None, description="Fraction with bidirectional confidence movement"
    )
    sample_size: int = 0


class ConfidenceDynamicsMetrics(BaseModel):
    """How beliefs respond to evidence over the lifecycle."""

    mean_absolute_drift: Optional[float] = Field(
        None, description="Mean |final_confidence - initial_confidence|"
    )
    mean_update_magnitude: Optional[float] = Field(
        None, description="Mean |delta confidence| per evidence item"
    )
    premature_conclusion_rate: Optional[float] = Field(
        None, description="Fraction concluded before deadline and later revised"
    )
    sample_size: int = 0


class LearningRateMetrics(BaseModel):
    """Is the system getting better over time?"""

    slope: Optional[float] = Field(
        None, description="Linear regression slope on rolling Brier scores (negative = improving)"
    )
    interpretation: str = Field(
        "insufficient_data",
        description="improving / stable / declining / insufficient_data",
    )
    insight_count: int = Field(0, description="Total insights created by this tenant")
    sample_size: int = 0


class MetricsResponse(BaseModel):
    """Core prediction quality metrics."""

    brier: BrierScoreMetrics = Field(default_factory=BrierScoreMetrics)
    calibration: CalibrationMetrics = Field(default_factory=CalibrationMetrics)
    prediction_value: PredictionValueMetrics = Field(default_factory=PredictionValueMetrics)
    falsification: FalsificationRigorMetrics = Field(default_factory=FalsificationRigorMetrics)
    confidence_dynamics: ConfidenceDynamicsMetrics = Field(
        default_factory=ConfidenceDynamicsMetrics
    )
    learning_rate: LearningRateMetrics = Field(default_factory=LearningRateMetrics)
    concluded_count: int = Field(0, description="Total supported + refuted hypotheses")
    total_count: int = Field(0, description="Total non-archived hypotheses")
