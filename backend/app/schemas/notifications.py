from datetime import datetime

from pydantic import BaseModel

from app.schemas.videos import VideoCardOut


class NotificationItem(VideoCardOut):
    published_at: datetime


class NotificationPage(BaseModel):
    items: list[NotificationItem]
    next_cursor: int | None
    seen_at: datetime  # когда пользователь последний раз открывал уведомления


class NotificationCount(BaseModel):
    count: int  # не больше COUNT_CAP, фронт показывает «99+»