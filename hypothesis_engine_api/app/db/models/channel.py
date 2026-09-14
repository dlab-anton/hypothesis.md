import uuid
from typing import Optional

from sqlalchemy import String, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base_class import Base


class Channel(Base):
    __tablename__ = "channels"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    updated_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("name", "tenant_id", name="uq_channels_name_tenant"),
        Index("ix_channels_tenant_id", "tenant_id"),
    )
