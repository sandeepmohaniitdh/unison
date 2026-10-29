from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import IstDateTime


class AiStatus(BaseModel):
    enabled: bool = Field(description="False on a fresh clone without an API key: the button is disabled.")
    provider: Literal["none", "gemini", "ollama", "fake"]
    model: str
    max_chars: int
    requests_per_submission: int
    daily_cap_per_final: int


class DraftRequest(BaseModel):
    file_id: int | None = Field(None, description="The PDF to read, if the final has several.")


class Suggestion(BaseModel):
    criterion_id: int
    title: str
    max_points: Decimal
    points: Decimal
    comment: str


class AiDraftOut(BaseModel):
    id: int
    final_id: int
    file_id: int
    status: Literal["queued", "running", "ready", "failed"]
    model: str
    created_at: IstDateTime
    finished_at: IstDateTime | None
    error_code: str | None
    message: str | None = Field(description="For failed drafts, e.g. 'Feedback draft unavailable; review manually.'")
    truncation_note: str | None = Field(description="Shown when the report was longer than 12,000 characters.")
    injection_suspected: bool = Field(description="The report contains instruction-like text: check it by hand.")
    suggestions: list[Suggestion]


class DraftAllSkip(BaseModel):
    team_id: int
    reason: str


class DraftAllOut(BaseModel):
    queued: int
    skipped: list[DraftAllSkip]
