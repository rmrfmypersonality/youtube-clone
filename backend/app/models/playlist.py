import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    func,
    text,
    true,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

WATCH_LATER_TITLE = "Смотреть позже"


class PlaylistKind(str, enum.Enum):
    regular = "regular"
    watch_later = "watch_later"  # системный: один на пользователя, всегда приватный


class Playlist(Base):
    __tablename__ = "playlists"
    __table_args__ = (
        CheckConstraint("kind IN ('regular', 'watch_later')", name="kind_valid"),
        CheckConstraint("kind <> 'watch_later' OR is_public IS FALSE", name="watch_later_private"),
        Index(
            "uq_playlists_watch_later",
            "owner_id",
            unique=True,
            postgresql_where=text("kind = 'watch_later'"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(5000), default="", server_default="")
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    kind: Mapped[PlaylistKind] = mapped_column(
        Enum(PlaylistKind, native_enum=False, length=16),
        default=PlaylistKind.regular,
        server_default=PlaylistKind.regular.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class PlaylistItem(Base):
    __tablename__ = "playlist_items"
    __table_args__ = (UniqueConstraint("playlist_id", "video_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)  # порядок добавления
    playlist_id: Mapped[int] = mapped_column(
        ForeignKey("playlists.id", ondelete="CASCADE"), index=True
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )