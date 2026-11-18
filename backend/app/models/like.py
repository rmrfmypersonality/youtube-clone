from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Identity, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Like(Base):
    """Реакция пользователя на видео: 1 = лайк, -1 = дизлайк.
    id задаёт порядок «последний лайк первым»: при смене реакции строка пересоздаётся."""

    __tablename__ = "likes"
    __table_args__ = (CheckConstraint("value IN (1, -1)", name="value_valid"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
        index=True,
    )
    id: Mapped[int] = mapped_column(Identity(always=False), unique=True)
    value: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )