from urllib.parse import urlsplit

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def is_allowed_origin(origin: str, host: str, extra: set[str] | frozenset[str] = frozenset()) -> bool:
    """Origin должен совпадать с Host запроса (или быть в списке разрешённых)."""
    origin = origin.strip().lower()
    if origin in extra:
        return True
    try:
        parts = urlsplit(origin)
    except ValueError:
        return False
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return False  # в том числе "null" и javascript:
    return parts.netloc == host.strip().lower()  # userinfo вида evil@host в netloc не совпадёт


class OriginCheckMiddleware:
    """CSRF-защита вторым слоем (первый: SameSite=Lax). Проверяет изменяющие запросы.

    Origin нет: пропускаем (не браузер, либо старый браузер; кросс-сайтовые куки Lax и так не отправит).
    Origin есть и не наш: 403 до любой логики приложения."""

    def __init__(self, app: ASGIApp, allowed_origins: set[str] | frozenset[str] = frozenset()) -> None:
        self.app = app
        self.allowed = frozenset(allowed_origins)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] not in SAFE_METHODS:
            headers = dict(scope["headers"])
            origin = headers.get(b"origin")
            if origin is not None:
                host = headers.get(b"host", b"").decode("latin-1")
                if not is_allowed_origin(origin.decode("latin-1"), host, self.allowed):
                    response = JSONResponse(
                        {"detail": "Запрос с чужого источника отклонён"}, status_code=403
                    )
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)