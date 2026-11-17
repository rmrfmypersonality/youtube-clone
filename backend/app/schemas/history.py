from pydantic import BaseModel

from app.schemas.videos import VideoCardOut


class HistoryPage(BaseModel):
    items: list[VideoCardOut]
    next_cursor: int | None  # id записи истории, не видео