from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field

from app.models import ReportReason, ReportStatus, Visibility
from app.schemas.common import NoNul


class ReportCreate(BaseModel):
    reason: ReportReason
    details: Annotated[str, Field(max_length=1000), NoNul] = ""


class ReportCreated(BaseModel):
    id: int


class UserBrief(BaseModel):
    id: int  # id пользователя
    handle: str
    name: str


class ReportVideoTarget(BaseModel):
    id: int
    title: str
    visibility: Visibility
    hidden: bool
    owner: UserBrief | None


class ReportCommentTarget(BaseModel):
    id: int
    video_id: int
    text: str
    hidden: bool
    author: UserBrief | None


class ReportItem(BaseModel):
    id: int
    status: ReportStatus
    reason: ReportReason
    details: str
    created_at: datetime
    handled_at: datetime | None
    reporter: UserBrief | None
    handled_by: UserBrief | None
    video: ReportVideoTarget | None
    comment: ReportCommentTarget | None


class ReportPage(BaseModel):
    items: list[ReportItem]
    next_cursor: int | None


class HiddenOut(BaseModel):
    hidden: bool