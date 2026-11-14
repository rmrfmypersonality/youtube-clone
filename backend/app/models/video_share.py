from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class VideoShare(Base):
    """Доступ к приватному видео для конкретного пользователя."""

    __tablename__ = "video_shares"

    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )