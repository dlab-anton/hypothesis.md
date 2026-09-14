import json
import re
from typing import Generic, TypeVar
from pydantic import BaseModel

T = TypeVar("T")

# --- Shared validation constants ---
MAX_JSON_BYTES = 65536  # 64KB per JSON field
MAX_JSON_DEPTH = 20  # Max nesting depth for JSONB fields
MAX_TAGS = 50
MAX_TAG_LENGTH = 100
CREATED_BY_PATTERN = re.compile(r'^[\w\-\.@\s]+$')
MOTIVE_ACTOR_PATTERN = r'motive:project:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
ACTOR_FILTER_PATTERN = rf'^(?:[\w\-\.@\s]+|{MOTIVE_ACTOR_PATTERN})$'


def _check_json_depth(obj: object, current: int = 0) -> int:
    """Return the maximum nesting depth of a JSON-like structure."""
    if current > MAX_JSON_DEPTH:
        return current  # early exit
    if isinstance(obj, dict):
        if not obj:
            return current
        return max(_check_json_depth(v, current + 1) for v in obj.values())
    if isinstance(obj, list):
        if not obj:
            return current
        return max(_check_json_depth(v, current + 1) for v in obj)
    return current


def validate_json_size(v: dict | None, field_name: str = "field") -> dict | None:
    """Reject JSON dicts larger than 64KB or nested deeper than MAX_JSON_DEPTH."""
    if v is not None:
        if _check_json_depth(v) > MAX_JSON_DEPTH:
            raise ValueError(f"{field_name} exceeds maximum nesting depth of {MAX_JSON_DEPTH}")
        if len(json.dumps(v, default=str)) > MAX_JSON_BYTES:
            raise ValueError(f"{field_name} must be under 64KB")
    return v


def validate_created_by(v: str | None) -> str | None:
    """Validate display attribution; this never establishes identity or authority."""
    if v is not None:
        v = v.strip()
        if not CREATED_BY_PATTERN.fullmatch(v) and not re.fullmatch(MOTIVE_ACTOR_PATTERN, v):
            raise ValueError("created_by contains invalid characters (allowed: letters, numbers, - . @ space)")
    return v


def validate_tags(v: list[str] | None, *, required: bool = False) -> list[str] | None:
    """Shared tag normalization: strip, lowercase, truncate, enforce max count."""
    if v is None:
        return None
    tags = [tag.strip().lower()[:MAX_TAG_LENGTH] for tag in v if tag.strip()]
    if len(tags) > MAX_TAGS:
        raise ValueError(f"Maximum {MAX_TAGS} tags allowed")
    return tags


def normalize_channel(v: str | None) -> str | None:
    """Shared channel normalization: strip, lowercase, spaces to hyphens."""
    if v is None:
        return None
    return v.strip().lower().replace(" ", "-")


def validate_label(v: str | None) -> str | None:
    """Restrict label to safe characters."""
    if v is not None:
        v = v.strip()
        if not CREATED_BY_PATTERN.match(v):
            raise ValueError("label contains invalid characters (allowed: letters, numbers, - . @ space)")
    return v


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class TagCount(BaseModel):
    tag: str
    count: int


class StatsResponse(BaseModel):
    total: int
    by_status: dict[str, int]
    avg_confidence: float | None
    total_evidence: int
    top_tags: list[TagCount]
    recent_count_7d: int
