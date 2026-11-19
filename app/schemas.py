from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class ReserveRequest(BaseModel):
    reservation_id: str = Field(min_length=36, max_length=36)
    purpose: Literal["structured", "hot-take"]


class ReleaseRequest(BaseModel):
    reservation_id: str = Field(min_length=36, max_length=36)


class AttemptPayload(BaseModel):
    transcript: str = Field(min_length=5, max_length=12000)
    scorecard: dict[str, Any]
    inference_source: Literal["ON_DEVICE", "IN_CLOUD", "UNKNOWN"] = "UNKNOWN"
    duration_seconds: int = Field(ge=1, le=120)
    filler_count: int = Field(ge=0, le=500)


class CreateSessionRequest(AttemptPayload):
    session_id: str = Field(min_length=36, max_length=36)
    reservation_id: str = Field(min_length=36, max_length=36)
    mode: Literal["structured", "hot-take"]
    goal: str = Field(default="", max_length=80)
    category: str = Field(default="", max_length=80)
    heat: str = Field(default="", max_length=20)
    prompt: str = Field(min_length=8, max_length=700)
    constraint_phrase: str = Field(default="", max_length=100)

    @field_validator("session_id", "reservation_id")
    @classmethod
    def valid_uuid(cls, value: str) -> str:
        import uuid
        uuid.UUID(value)
        return value


class RetryRequest(AttemptPayload):
    pass
