import uuid
from typing import Optional

from sqlalchemy import String, Text, Float, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_class import Base


class Evidence(Base):
    __tablename__ = "evidence"

    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(20), nullable=False)
    strength: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence_after: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    hypothesis = relationship("Hypothesis", back_populates="evidence")

    __table_args__ = (
        Index("ix_evidence_hypothesis_id", "hypothesis_id"),
        Index("ix_evidence_type", "evidence_type"),
        Index("ix_evidence_created_at", "created_at"),
        Index("ix_evidence_created_by", "created_by"),
    )
