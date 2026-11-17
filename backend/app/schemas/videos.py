from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.models import VideoStatus, Visibility
from app.schemas.auth import USERNAME_RE, ChannelBrief
from app.schemas.common import NoNul
from app.core.params import INT_MAX

Title = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100), NoNul
]
Description = Annotated[str, Field(max_length=5000), NoNul]
Quality = Literal["720", "360"]
CategoryId = Annotated[int, Field(ge=1, le=INT_MAX)]


class VideoCreate(BaseModel):
    title: Title
    description: Description = ""
    visibility: Visibility = Visibility.private
    category_id: CategoryId | None = None  # None = «Другое»


class VideoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    title: str
    description: str
    status: VideoStatus
    visibility: Visibility
    category_id: int
    hidden_by_moderation: bool
    duration_seconds: float | None
    views_count: int
    created_at: datetime


class VideoDetailOut(VideoOut):
    channel: ChannelBrief
    likes_count: int
    my_reaction: int  # 1, -1 или 0
    subscribers_count: int
    is_subscribed: bool


class VideoUpdate(BaseModel):
    """Все поля необязательные; None = не менять."""

    title: Title | None = None
    description: Description | None = None
    visibility: Visibility | None = None
    category_id: CategoryId | None = None


class VideoManagePage(BaseModel):
    items: list[VideoOut]
    next_cursor: int | None


class VideoCardOut(BaseModel):
    id: int
    title: str
    duration_seconds: float | None
    views_count: int
    created_at: datetime
    channel: ChannelBrief


class VideoPage(BaseModel):
    items: list[VideoCardOut]
    next_cursor: int | None


class ViewCountOut(BaseModel):
    views_count: int


class ShareIn(BaseModel):
    username: str = Field(pattern=USERNAME_RE)


class SharedUserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str