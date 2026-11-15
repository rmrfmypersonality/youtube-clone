import enum
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Index, String, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class ReportStatus(str, enum.Enum):
    open = "open"
    resolved = "resolved"  # модератор скрыл цель
    dismissed = "dismissed"  # жалоба отклонена


class ReportReason(str, enum.Enum):
    spam = "spam"
    abuse = "abuse"
    violence = "violence"
    copyright = "copyright"
    other = "other"


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("num_nonnulls(video_id, comment_id) = 1", name="exactly_one_target"),
        CheckConstraint("status IN ('open', 'resolved', 'dismissed')", name="status_valid"),
        CheckConstraint(
            "reason IN ('spam', 'abuse', 'violence', 'copyright', 'other')", name="reason_valid"
        ),
        # Один пользователь: одна открытая жалоба на одну цель
        Index(
            "uq_reports_open_video",
            "reporter_id",
            "video_id",
            unique=True,
            postgresql_where=text("status = 'open' AND video_id IS NOT NULL"),
        ),
        Index(
            "uq_reports_open_comment",
            "reporter_id",
            "comment_id",
            unique=True,
            postgresql_where=text("status = 'open' AND comment_id IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("videos.id", ondelete="CASCADE"), index=True
    )
    comment_id: Mapped[int | None] = mapped_column(
        ForeignKey("comments.id", ondelete="CASCADE"), index=True
    )
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[ReportReason] = mapped_column(Enum(ReportReason, native_enum=False, length=16))
    details: Mapped[str] = mapped_column(String(1000), default="", server_default="")
    status: Mapped[ReportStatus] = mapped_column(
        Enum(ReportStatus, native_enum=False, length=16),
        default=ReportStatus.open,
        server_default=ReportStatus.open.value,
        index=True,
    )
    handled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    handled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )