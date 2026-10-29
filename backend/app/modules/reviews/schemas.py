from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

from app.core.time import IstDateTime
from app.modules.assignments.schemas import SubmissionState
from app.modules.submissions.schemas import FinalOut
from app.modules.users.schemas import UserBrief

ReviewStatus = Literal["none", "draft", "released"]


class ScoreIn(BaseModel):
    criterion_id: int
    points: Decimal = Field(ge=0, decimal_places=1, examples=[8.5])
    comment: str | None = Field(None, max_length=2000)


class ReviewIn(BaseModel):
    overall_comment: str | None = Field(None, max_length=5000)
    scores: list[ScoreIn] = Field(default_factory=list, description="Criteria not listed keep their current score.")


class ReleaseIn(BaseModel):
    status: Literal["released"]


class AdjustmentIn(BaseModel):
    percent: Decimal = Field(ge=-20, le=10, decimal_places=1, description="Of the team mark, from -20 to +10.")
    reason: str = Field(min_length=3, max_length=2000, description="Shown to the member.")


class CriterionScore(BaseModel):
    criterion_id: int
    position: int
    title: str
    max_points: Decimal
    points: Decimal | None
    comment: str | None


class Contribution(BaseModel):
    user: UserBrief
    status: str
    drafts_uploaded: int
    last_upload_at: IstDateTime | None
    submitted_current_final: bool


class MemberMark(BaseModel):
    user: UserBrief
    adjustment_percent: Decimal | None
    reason: str | None
    mark: Decimal | None = Field(description="Team mark plus the adjustment, kept between 0 and the maximum.")


class AssignmentRef(BaseModel):
    id: int
    title: str
    course_id: int


class ReviewSheet(BaseModel):
    team: UserBrief = Field(description="id and name of the team")
    assignment: AssignmentRef
    final: FinalOut
    replaced_finals: int
    contribution: list[Contribution] = Field(
        description="Activity from the draft history; draft content is never shown."
    )
    rubric: list[CriterionScore]
    overall_comment: str | None
    status: ReviewStatus
    released_at: IstDateTime | None
    team_mark: Decimal | None = Field(description="Sum of the scores, once every criterion is scored.")
    max_mark: Decimal
    members: list[MemberMark]


class ReviewRow(BaseModel):
    team: UserBrief
    member_count: int
    state: SubmissionState
    final_id: int | None
    version_number: int | None
    final_kind: Literal["manual", "at_deadline"] | None
    below_min_size: bool
    submitted_at: IstDateTime | None
    review_status: ReviewStatus
    team_mark: Decimal | None
    max_mark: Decimal


class ReleaseSkip(BaseModel):
    team_id: int
    reason: str


class BulkReleaseOut(BaseModel):
    released: int
    skipped: list[ReleaseSkip]


class MyMarks(BaseModel):
    assignment: AssignmentRef
    team: UserBrief
    rubric: list[CriterionScore]
    overall_comment: str | None
    team_mark: Decimal
    max_mark: Decimal
    adjustment_percent: Decimal | None
    adjustment_reason: str | None
    my_mark: Decimal
    released_at: IstDateTime
