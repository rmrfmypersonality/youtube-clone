from typing import Annotated

from fastapi import APIRouter, Depends, Request
from starlette.requests import ClientDisconnect

from app.core.deps import CurrentUser, SessionDep, StorageDep
from app.core.exceptions import AppError
from app.schemas.videos import VideoCreate, VideoOut
from app.services.videos import VideoService

router = APIRouter(prefix="/api/videos", tags=["videos"])


def get_video_service(session: SessionDep, storage: StorageDep) -> VideoService:
    return VideoService(session, storage)


VideoServiceDep = Annotated[VideoService, Depends(get_video_service)]


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
    video_id: int, request: Request, user: CurrentUser, service: VideoServiceDep
):
    """Сырое тело запроса = файл. Пишется на диск потоком, в память целиком не читается."""
    raw_length = request.headers.get("content-length")
    content_length = int(raw_length) if raw_length and raw_length.isdigit() else None
    try:
        return await service.upload_file(user, video_id, request.stream(), content_length)
    except ClientDisconnect:
        raise AppError("Загрузка прервана") from None


@router.get("/{video_id}", response_model=VideoOut)
async def get_video(video_id: int, user: CurrentUser, service: VideoServiceDep):
    return await service.get_manageable(user, video_id)