from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field

from app.core.time import IstDateTime
from app.modules.users.schemas import UserBrief


class LinkIn(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["Lecture 5 recording"])
    description: str | None = Field(None, max_length=5000)
    url: AnyHttpUrl = Field(examples=["https://example.com/lecture-5"])


class ResourceUpdate(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = Field(None, max_length=5000)
    url: AnyHttpUrl | None = Field(None, description="Links only.")


class PublishIn(BaseModel):
    resource_ids: list[int] = Field(min_length=1, max_length=100)
    notify: bool = Field(True, description="Untick to publish without notifying students.")


class ResourceOut(BaseModel):
    id: int
    course_id: int
    title: str
    description: str | None
    kind: Literal["file", "link"]
    file_name: str | None
    mime_type: str | None
    size_bytes: int | None
    url: str | None
    status: Literal["draft", "published"]
    published_at: IstDateTime | None
    created_by: UserBrief
    created_at: IstDateTime
