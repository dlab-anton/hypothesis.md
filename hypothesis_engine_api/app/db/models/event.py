import uuid

from sqlalchemy import String, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_class import Base


class Event(Base):
    __tablename__ = "events"

    hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default="{}")
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)

    # Relationships
    hypothesis = relationship("Hypothesis", back_populates="events")

    __table_args__ = (
        Index("ix_events_hypothesis_id", "hypothesis_id"),
        Index("ix_events_event_type", "event_type"),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_created_by", "created_by"),
    )
