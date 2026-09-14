import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, Float, Boolean, ForeignKey, Index, DateTime
from sqlalchemy.dialects.postgresql import ARRAY, UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_class import Base


class Hypothesis(Base):
    __tablename__ = "hypotheses"

    statement: Mapped[str] = mapped_column(Text, nullable=False)
    context: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    falsification_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="draft")
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    initial_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default="{}")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hypotheses.id"), nullable=True
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    null_hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    experimental_design: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    significance_level: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    outcome: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    channel: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Relationships
    evidence = relationship("Evidence", back_populates="hypothesis", cascade="all, delete-orphan", lazy="noload")
    events = relationship("Event", back_populates="hypothesis", cascade="all, delete-orphan", lazy="noload")
    parent = relationship("Hypothesis", remote_side="Hypothesis.id", foreign_keys=[parent_id], lazy="noload")

    __table_args__ = (
        Index("ix_hypotheses_status", "status"),
        Index("ix_hypotheses_created_by", "created_by"),
        Index("ix_hypotheses_tags", "tags", postgresql_using="gin"),
        Index("ix_hypotheses_parent_id", "parent_id"),
        Index("ix_hypotheses_created_at", "created_at"),
        Index("ix_hypotheses_confidence", "confidence"),
        Index("ix_hypotheses_deadline", "deadline"),
        Index("ix_hypotheses_channel", "channel"),
        Index("ix_hypotheses_tenant_id", "tenant_id"),
    )
