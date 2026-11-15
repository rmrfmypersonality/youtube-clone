from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

from app.core.params import INT_MAX
from app.schemas.common import NoNul

CommentText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000), NoNul
]


class CommentCreate(BaseModel):
    text: CommentText
    parent_id: int | None = Field(default=None, ge=1, le=INT_MAX)


class CommentAuthor(BaseModel):
    id: int  # id пользователя
    handle: str
    name: str


class CommentOut(BaseModel):
    id: int
    video_id: int
    parent_id: int | None
    text: str
    created_at: datetime
    author: CommentAuthor
    reply_count: int
    hidden_by_moderation: bool = False


class CommentPage(BaseModel):
    items: list[CommentOut]
    next_cursor: int | None