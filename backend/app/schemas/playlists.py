from datetime import datetime

from pydantic import BaseModel

from app.schemas.auth import ChannelBrief
from app.schemas.videos import Description, Title, VideoCardOut
from app.models import PlaylistKind, Visibility

class PlaylistCreate(BaseModel):
    title: Title
    description: Description = ""
    visibility: Visibility = Visibility.public


class PlaylistUpdate(BaseModel):
    title: Title | None = None
    description: Description | None = None
    visibility: Visibility | None = None


class PlaylistOut(BaseModel):
    id: int
    title: str
    description: str
    visibility: Visibility
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