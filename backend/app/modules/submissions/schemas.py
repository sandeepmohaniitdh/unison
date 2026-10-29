from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import IstDateTime
from app.modules.assignments.schemas import SubmissionState
from app.modules.users.schemas import UserBrief


class FileOut(BaseModel):
    id: int
    file_name: str
    mime_type: Literal["application/pdf", "application/zip"]
    size_bytes: int


class DraftOut(BaseModel):
    id: int
    number: int = Field(description="v1, v2, ... per team")
    uploaded_by: UserBrief
    created_at: IstDateTime
    files: list[FileOut]
    is_current_final: bool


class FinalOut(BaseModel):
    id: int
    version_id: int
    version_number: int
    submitted_by: UserBrief | None = Field(description="Empty when it was submitted automatically at the deadline.")
    kind: Literal["manual", "at_deadline"]
    below_min_size: bool
    submitted_at: IstDateTime
    replaced_at: IstDateTime | None
    files: list[FileOut]


class SubmissionOut(BaseModel):
    team_id: int
    assignment_id: int
    state: SubmissionState
    due_at: IstDateTime
    closed_at: IstDateTime | None = Field(description="Set when the deadline was applied.")
    current_final: FinalOut | None
    replaced_finals: int = Field(description="How many earlier finals this one replaced.")
    drafts_count: int | None = Field(description="Team members only.")


class FinalIn(BaseModel):
    version_id: int = Field(description="The draft to submit as the team's final.")
    expected_final_id: int | None = Field(
        description="The current final the member last saw (null if none). If a teammate changed it "
        "in the meantime, the request fails with 409 FINAL_CHANGED."
    )
