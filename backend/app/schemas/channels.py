from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.auth import USERNAME_RE
from app.schemas.videos import Description, Title


class ChannelOut(BaseModel):
    id: int
    handle: str
    name: str
    description: str
    created_at: datetime
    subscribers_count: int
    videos_count: int  # только публичные готовые
    is_subscribed: bool
    is_owner: bool
    is_hidden: bool  # true бывает только в ответе владельцу: остальным канал отдаёт 404


class ChannelUpdate(BaseModel):
    name: Title | None = None
    handle: str | None = Field(default=None, pattern=USERNAME_RE)
    description: Description | None = None
    is_hidden: bool | None = None


class SubscriptionOut(BaseModel):
    subscribed: bool
    subscribers_count: int