from fastapi import APIRouter, Response

from app.core.deps import CurrentUser, SessionDep, StorageDep
from app.routers.auth import clear_auth_cookies
from app.schemas.account import AccountDelete
from app.services.account import AccountService

router = APIRouter(prefix="/api/account", tags=["account"])


@router.post("/delete", status_code=204)
async def delete_account(
    data: AccountDelete,
    response: Response,
    user: CurrentUser,
    session: SessionDep,
    storage: StorageDep,
) -> None:
    """Безвозвратно удаляет аккаунт, канал и весь контент. Требует пароль."""
    await AccountService(session, storage).delete(user, data.password)
    clear_auth_cookies(response)