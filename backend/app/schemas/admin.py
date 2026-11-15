from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.models import Role
from app.schemas.moderation import UserBrief


class UserAdminOut(BaseModel):
    id: int
    username: str
    email: str
    role: Role
    is_active: bool
    created_at: datetime
    channel_handle: str


class UserAdminUpdate(BaseModel):
    """None = не менять."""

    role: Role | None = None
    is_active: bool | None = None


class UserAdminPage(BaseModel):
    items: list[UserAdminOut]
    next_cursor: int | None


class AuditOut(BaseModel):
    id: int
    actor: UserBrief | None
    action: str
    target_type: str
    target_id: int | None
    details: dict[str, Any] | None
    created_at: datetime


class AuditPage(BaseModel):
    items: list[AuditOut]
    next_cursor: int | None