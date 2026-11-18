from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CommentLike(Base):
    """Реакция на комментарий: 1 = лайк, -1 = дизлайк."""

    __tablename__ = "comment_likes"
    __table_args__ = (CheckConstraint("value IN (1, -1)", name="value_valid"),)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False
    )
    comment_id: Mapped[int] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"),
        primary_key=True,
        autoincrement=False,
        index=True,
    )
    value: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )