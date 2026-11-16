from typing import Annotated

from fastapi import APIRouter, Cookie, Response

from app.core.config import get_settings
from app.core.deps import CurrentUser, SessionDep
from app.core.exceptions import Unauthorized
from app.schemas.auth import LoginIn, RegisterIn, UserOut
from app.services.auth import AuthResult, AuthService

router = APIRouter(prefix="/api/auth", tags=["auth"])

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
REFRESH_PATH = "/api/auth"  # refresh-кука уходит только на auth-эндпоинты


def _set_auth_cookies(response: Response, result: AuthResult) -> None:
    s = get_settings()
    response.set_cookie(
        ACCESS_COOKIE,
        result.access_token,
        max_age=s.access_token_ttl_minutes * 60,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        result.refresh_token,
        max_age=s.refresh_token_ttl_days * 86400,
        httponly=True,
        secure=s.cookie_secure,
        samesite="lax",
        path=REFRESH_PATH,
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_PATH)


@router.post("/register", response_model=UserOut, status_code=201)
async def register(data: RegisterIn, response: Response, session: SessionDep):
    result = await AuthService(session).register(data)
    _set_auth_cookies(response, result)
    return result.user


@router.post("/login", response_model=UserOut)
async def login(data: LoginIn, response: Response, session: SessionDep):
    result = await AuthService(session).login(data)
    _set_auth_cookies(response, result)
    return result.user


@router.post("/refresh", response_model=UserOut)
async def refresh(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
):
    if not refresh_token:
        raise Unauthorized()
    result = await AuthService(session).refresh(refresh_token)
    _set_auth_cookies(response, result)
    return result.user


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    session: SessionDep,
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> None:
    if refresh_token:
        await AuthService(session).logout(refresh_token)
    clear_auth_cookies(response)


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser):
    return user