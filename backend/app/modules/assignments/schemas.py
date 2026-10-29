from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.core.time import IstDateTime, IstDateTimeIn

SubmissionState = Literal[
    "no_team", "no_work", "drafts", "final_submitted", "submitted_at_deadline", "not_submitted", "marks_released"
]


class CriterionIn(BaseModel):
    title: str = Field(min_length=1, max_length=160, examples=["Design quality"])
    max_points: Decimal = Field(gt=0, le=1000, decimal_places=1, examples=[10])


class CriterionOut(BaseModel):
    id: int
    position: int
    title: str
    max_points: Decimal


class AssignmentIn(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Project report"])
    description: str | None = Field(None, max_length=20000)
    kind: Literal["individual", "group"]
    min_team: int = Field(1, ge=1, le=20)
    max_team: int = Field(1, ge=1, le=20)
    max_files: int = Field(5, ge=1, le=5)
    requires_pdf: bool = Field(False, description="Every final must contain a PDF report (needed for AI drafts).")
    due_at: IstDateTimeIn
    rubric: list[CriterionIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _sizes(self):
        if self.kind == "individual":
            self.min_team = self.max_team = 1
        if self.max_team < self.min_team:
            raise ValueError("max_team must be at least min_team")
        return self


class AssignmentUpdate(BaseModel):
    """Only the fields sent are changed. After publishing: title, description,
    a later due_at (an extension) and teams_locked."""

    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=20000)
    kind: Literal["individual", "group"] | None = None
    min_team: int | None = Field(None, ge=1, le=20)
    max_team: int | None = Field(None, ge=1, le=20)
    max_files: int | None = Field(None, ge=1, le=5)
    requires_pdf: bool | None = None
    due_at: IstDateTimeIn | None = None
    rubric: list[CriterionIn] | None = Field(None, min_length=1, max_length=20)
    teams_locked: bool | None = Field(None, description="Group assignments: freeze all team changes.")
    status: Literal["published"] | None = Field(None, description="'published' publishes a draft.")


class MyTeam(BaseModel):
    team_id: int | None
    state: SubmissionState


class AssignmentSummary(BaseModel):
    id: int
    course_id: int
    title: str
    kind: Literal["individual", "group"]
    min_team: int
    max_team: int
    due_at: IstDateTime
    status: Literal["draft", "published", "closed"]
    teams_locked: bool
    total_points: Decimal
    my_team: MyTeam | None = Field(None, description="For students: their team and its state.")


class AssignmentDetail(AssignmentSummary):
    description: str | None
    max_files: int
    requires_pdf: bool
    published_at: IstDateTime | None
    rubric: list[CriterionOut]
