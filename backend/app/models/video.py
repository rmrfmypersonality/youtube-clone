import enum
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    String,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VideoStatus(str, enum.Enum):
    pending = "pending"  # запись создана, файл ещё не загружен
    uploaded = "uploaded"  # файл на диске, ждёт воркера
    processing = "processing"
    ready = "ready"
    failed = "failed"


class Visibility(str, enum.Enum):
    public = "public"
    unlisted = "unlisted"
    private = "private"


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'uploaded', 'processing', 'ready', 'failed')",
            name="status_valid",
        ),
        CheckConstraint(
            "visibility IN ('public', 'unlisted', 'private')", name="visibility_valid"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(5000), default="", server_default="")
    status: Mapped[VideoStatus] = mapped_column(
        Enum(VideoStatus, native_enum=False, length=16),
        default=VideoStatus.pending,
        server_default=VideoStatus.pending.value,
    )
    visibility: Mapped[Visibility] = mapped_column(
        Enum(Visibility, native_enum=False, length=16),
        default=Visibility.private,
        server_default=Visibility.private.value,
    )
    hidden_by_moderation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    # Ключи в Storage, не абсолютные пути
    original_path: Mapped[str | None] = mapped_column(String(512))
    path_720: Mapped[str | None] = mapped_column(String(512))
    path_360: Mapped[str | None] = mapped_column(String(512))
    thumbnail_path: Mapped[str | None] = mapped_column(String(512))
    duration_seconds: Mapped[float | None] = mapped_column(Float)
    views_count: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )