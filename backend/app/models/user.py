import enum
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, String, func, true
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Role(str, enum.Enum):
    user = "user"
    moderator = "moderator"
    admin = "admin"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'moderator', 'admin')", name="role_valid"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT, unique=True)
    username: Mapped[str] = mapped_column(CITEXT, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(
        Enum(Role, native_enum=False, length=16),
        default=Role.user,
        server_default=Role.user.value,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    # Колокольчик: видео подписок, опубликованные позже этого момента, считаются новыми
    notifications_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # joined: в async нельзя лениво подгружать, канал нужен почти всегда
    channel: Mapped["Channel"] = relationship(  # noqa: F821
        uselist=False, lazy="joined", cascade="all, delete-orphan"
    )