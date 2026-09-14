import uuid
from typing import Optional

from sqlalchemy import String, Text, Index
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base_class import Base


class Insight(Base):
    __tablename__ = "insights"

    channel: Mapped[str] = mapped_column(String(100), nullable=False)
    insight_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        Index("ix_insights_channel", "channel"),
        Index("ix_insights_channel_type", "channel", "insight_type"),
        Index("ix_insights_tenant_id", "tenant_id"),
    )
