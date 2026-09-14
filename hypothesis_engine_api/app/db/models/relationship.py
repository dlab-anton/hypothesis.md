import uuid
from typing import Optional

from sqlalchemy import String, ForeignKey, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base_class import Base


class Relationship(Base):
    __tablename__ = "relationships"

    source_hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    target_hypothesis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("hypotheses.id", ondelete="CASCADE"), nullable=False
    )
    relationship_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    source_hypothesis = relationship(
        "Hypothesis", foreign_keys=[source_hypothesis_id], lazy="noload"
    )
    target_hypothesis = relationship(
        "Hypothesis", foreign_keys=[target_hypothesis_id], lazy="noload"
    )

    __table_args__ = (
        Index("ix_relationships_source", "source_hypothesis_id"),
        Index("ix_relationships_target", "target_hypothesis_id"),
        UniqueConstraint(
            "source_hypothesis_id", "target_hypothesis_id", "relationship_type",
            name="uq_relationships_source_target_type",
        ),
        Index("ix_relationships_tenant_id", "tenant_id"),
    )
