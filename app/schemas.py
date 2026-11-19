from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


class ScorecardValidationRequest(BaseModel):
    transcript: str = Field(min_length=5, max_length=12000)
    scorecard: dict[str, Any]
    mode: Literal["structured", "hot-take"]
