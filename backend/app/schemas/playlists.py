from datetime import datetime

from pydantic import BaseModel

from app.schemas.auth import ChannelBrief
from app.schemas.videos import Description, Title, VideoCardOut
from app.models import PlaylistKind

class PlaylistCreate(BaseModel):
    title: Title
    description: Description = ""
    is_public: bool = True


class PlaylistUpdate(BaseModel):
    title: Title | None = None
    description: Description | None = None
    is_public: bool | None = None


class PlaylistOut(BaseModel):
    id: int
    title: str
    description: str
    is_public: bool
    kind: PlaylistKind
    created_at: datetime
    items_count: int
    cover_video_id: int | None
    channel: ChannelBrief


class PlaylistMineOut(PlaylistOut):
    contains: bool  # есть ли в плейлисте видео из запроса ?video_id=


class PlaylistDetailOut(PlaylistOut):
    items: list[VideoCardOut]
    is_owner: bool