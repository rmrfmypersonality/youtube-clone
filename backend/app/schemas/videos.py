from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import VideoStatus, Visibility
from app.schemas.auth import USERNAME_RE, ChannelBrief
from app.schemas.common import NoNul

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100), NoNul
]
Description = Annotated[str, Field(max_length=5000), NoNul]
Quality = Literal["720", "360"]


class VideoCreate(BaseModel):
    title: Title
    description: Description = ""
    visibility: Visibility = Visibility.private


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    title: str
    description: str
    status: VideoStatus
    visibility: Visibility
    hidden_by_moderation: bool
    duration_seconds: float | None
    views_count: int
    created_at: datetime


class VideoDetailOut(VideoOut):
    channel: ChannelBrief


class ViewCountOut(BaseModel):
    views_count: int


class ShareIn(BaseModel):
    username: str = Field(pattern=USERNAME_RE)


class SharedUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str