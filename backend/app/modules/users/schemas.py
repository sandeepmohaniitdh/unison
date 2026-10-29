from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.core.time import IstDateTime


class UserBrief(BaseModel):
    id: int
    name: str


class EmailOut(BaseModel):
    id: int
    email: str
    is_primary: bool
    verified: bool


class MeOut(BaseModel):
    id: int
    name: str
    role: Literal["student", "teacher", "admin"]
    status: str
    emails: list[EmailOut]
    has_password: bool
    google_linked: bool
    must_change_password: bool
    created_at: IstDateTime


class ProfileUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120, examples=["Sandeep M"])


class PasswordChange(BaseModel):
    current_password: str | None = Field(
        None, description="Leave out if the account has no password yet (Google only)."
    )
    new_password: str = Field(min_length=8, max_length=128)


class EmailAdd(BaseModel):
    email: EmailStr = Field(examples=["sandeep.personal@example.com"])


class EmailUpdate(BaseModel):
    is_primary: Literal[True] = Field(description="Only true is allowed: it makes this email the primary one.")


class DeletionPreview(BaseModel):
    running_courses: int
    active_teams: int
    grace_days: int
    can_delete: bool = Field(description="False for the last administrator.")


class DeletionRequest(BaseModel):
    password: str | None = Field(
        None, description="Required for accounts with a password. Google-only accounts sign in again first."
    )


class DeletionOut(BaseModel):
    status: Literal["deactivated"]
    final_deletion_at: IstDateTime
    message: str
