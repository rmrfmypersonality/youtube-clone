from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request, Response
from starlette.requests import ClientDisconnect

from app.core.deps import CurrentUser, OptionalUser, SessionDep, StorageDep
from app.core.exceptions import AppError
from app.schemas.videos import (
    Quality,
    SharedUserOut,
    ShareIn,
    VideoCreate,
    VideoDetailOut,
    VideoOut,
    ViewCountOut,
)
from app.services.videos import VideoService

router = APIRouter(prefix="/api/videos", tags=["videos"])

INT_MAX = 2_147_483_647  # иначе asyncpg на огромном id падает 500, а не 422
VideoId = Annotated[int, Path(ge=1, le=INT_MAX)]
UserId = Annotated[int, Path(ge=1, le=INT_MAX)]

# private: чужие кеши (прокси) не должны сохранять защищённые файлы
STREAM_CACHE = "private, no-cache"
THUMB_CACHE = "private, max-age=300"


def get_video_service(session: SessionDep, storage: StorageDep) -> VideoService:
    return VideoService(session, storage)


VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]


def _accel(path: str, cache_control: str) -> Response:
    # Тело пустое: файл отдаёт nginx (с Range) по заголовку X-Accel-Redirect.
    # Content-Type не ставим, nginx определит его по расширению файла.
    return Response(headers={"X-Accel-Redirect": path, "Cache-Control": cache_control})


@router.post("", response_model=VideoOut, status_code=201)
async def create_video(data: VideoCreate, user: CurrentUser, service: VideoServiceDep):
    return await service.create(user, data)


@router.put(
    "/{video_id}/file",
    response_model=VideoOut,
    status_code=202,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/octet-stream": {"schema": {"type": "string", "format": "binary"}}
            },
        }
    },
)
async def upload_video_file(
    video_id: VideoId, request: Request, user: CurrentUser, service: VideoServiceDep
):
    """Сырое тело запроса = файл. Пишется на диск потоком, в память целиком не читается."""
    raw_length = request.headers.get("content-length")
    content_length = int(raw_length) if raw_length and raw_length.isdigit() else None
    try:
        return await service.upload_file(user, video_id, request.stream(), content_length)
    except ClientDisconnect:
        raise AppError("Загрузка прервана") from None


@router.get("/{video_id}", response_model=VideoDetailOut)
async def get_video(video_id: VideoId, user: OptionalUser, service: VideoServiceDep):
    return await service.get_visible(user, video_id)


@router.get(
    "/{video_id}/stream",
    response_class=Response,
    responses={200: {"content": {"video/mp4": {}}}},
)
async def stream_video(
    video_id: VideoId,
    user: OptionalUser,
    service: VideoServiceDep,
    quality: Quality = "720",
):
    """Проверяет права и отдаёт файл через nginx (X-Accel-Redirect). Только через nginx, не напрямую."""
    return _accel(await service.stream_target(user, video_id, quality), STREAM_CACHE)


@router.get(
    "/{video_id}/thumbnail",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
async def video_thumbnail(video_id: VideoId, user: OptionalUser, service: VideoServiceDep):
    return _accel(await service.thumbnail_target(user, video_id), THUMB_CACHE)


@router.post("/{video_id}/view", response_model=ViewCountOut)
async def register_view(video_id: VideoId, user: OptionalUser, service: VideoServiceDep):
    return ViewCountOut(views_count=await service.record_view(user, video_id))


@router.get("/{video_id}/shares", response_model=list[SharedUserOut])
async def list_shares(video_id: VideoId, user: CurrentUser, service: VideoServiceDep):
    return await service.list_shares(user, video_id)


@router.post("/{video_id}/shares", response_model=SharedUserOut, status_code=201)
async def add_share(
    video_id: VideoId, data: ShareIn, user: CurrentUser, service: VideoServiceDep
):
    return await service.add_share(user, video_id, data.username)


@router.delete("/{video_id}/shares/{user_id}", status_code=204)
async def remove_share(
    video_id: VideoId, user_id: UserId, user: CurrentUser, service: VideoServiceDep
) -> None:
    await service.remove_share(user, video_id, user_id)