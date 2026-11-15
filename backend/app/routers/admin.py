from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import AdminUser, SessionDep
from app.core.params import CursorQuery, IdPath, LimitQuery
from app.schemas.admin import AuditPage, UserAdminOut, UserAdminPage, UserAdminUpdate
from app.services.admin import AdminService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.get("/users", response_model=UserAdminPage)
async def list_users(
    admin: AdminUser,
    session: SessionDep,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: CursorQuery = None,
    limit: LimitQuery = 20,
):
    """Поиск по username и email (подстрока), новые первыми."""
    return await AdminService(session).list_users(q=q, cursor=cursor, limit=limit)


@router.patch("/users/{user_id}", response_model=UserAdminOut)
async def update_user(
    user_id: IdPath, data: UserAdminUpdate, admin: AdminUser, session: SessionDep
):
    return await AdminService(session).update_user(admin, user_id, data)


@router.get("/audit", response_model=AuditPage)
async def list_audit(
    admin: AdminUser, session: SessionDep, cursor: CursorQuery = None, limit: LimitQuery = 30
):
    return await AdminService(session).list_audit(cursor=cursor, limit=limit)