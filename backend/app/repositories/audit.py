from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog, Channel, User


class AuditRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def log(
        self,
        actor: User,
        action: str,
        target_type: str,
        target_id: int | None,
        details: dict | None = None,
    ) -> None:
        """Только добавляет запись в сессию: коммитит вызывающий вместе с самим действием."""
        self.session.add(
            AuditLog(
                actor_id=actor.id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                details=details,
            )
        )

    async def list_page(
        self, *, cursor: int | None, limit: int
    ) -> list[tuple[AuditLog, Channel | None]]:
        stmt = (
            select(AuditLog, Channel)
            .outerjoin(Channel, Channel.owner_id == AuditLog.actor_id)
            .order_by(AuditLog.id.desc())
            .limit(limit + 1)
        )
        if cursor is not None:
            stmt = stmt.where(AuditLog.id < cursor)
        return [(r.AuditLog, r.Channel) for r in (await self.session.execute(stmt)).all()]