import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class EventRead(BaseModel):
    id: uuid.UUID
    hypothesis_id: uuid.UUID
    event_type: str
    data: dict[str, Any]
    created_by: str
    created_at: datetime

    model_config = {"from_attributes": True}
