from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, false, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (
        # Сортировка «Сначала популярные» внутри видео
        Index("ix_comments_video_popular", "video_id", "likes_count", "id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    # Только один уровень вложенности: parent_id всегда указывает на корневой комментарий
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    text: Mapped[str] = mapped_column(String(2000))
    hidden_by_moderation: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default=false()
    )
    # Денормализованный счётчик лайков, пересчитывается при каждой реакции
    likes_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )