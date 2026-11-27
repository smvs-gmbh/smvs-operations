"""Bounded file commands shared with the stateless participant gateway."""
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

MAX_BYTES = 5 * 1024 * 1024
MAX_FILES = 5
MAX_JSON = 7 * 1024 * 1024


class Upload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    submission_key: UUID
    basis: str = Field(pattern=r'^[a-f0-9]{64}$')
    filename: str = Field(min_length=1, max_length=255)
    content: str = Field(min_length=1, max_length=MAX_JSON)

