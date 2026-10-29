from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.time import IstDateTime
from app.modules.assignments.schemas import SubmissionState
from app.modules.users.schemas import UserBrief


class TeamIn(BaseModel):
    name: str = Field(min_length=1, max_length=80, examples=["Byte Builders"])


class TeamMemberOut(BaseModel):
    user: UserBrief
    status: Literal["active", "removed", "former"]
    joined_at: IstDateTime


class PendingInvitation(BaseModel):
    id: int
    email: str
    invited_by: UserBrief
    expires_at: IstDateTime


class TeamOut(BaseModel):
    id: int
    name: str
    assignment_id: int
    course_id: int
    kind: Literal["individual", "group"]
    min_team: int
    max_team: int
    closed: bool
    created_by: int
    members: list[TeamMemberOut]
    pending_invitations: list[PendingInvitation] = Field(description="Shown to team members only.")
    places_left: int = Field(description="max_team minus active members and pending invitations.")
    has_final: bool = Field(description="True once any final was submitted; members can no longer leave.")
    state: SubmissionState


class MemberMove(BaseModel):
    team_id: int = Field(description="The team to move the member to.")


class TeamInvitationIn(BaseModel):
    email: EmailStr = Field(examples=["cs26mt025@iitdh.ac.in"])
