from typing import Annotated

from fastapi import APIRouter, Query

from app.core.deps import CurrentUser, OptionalUser, SessionDep
from app.core.params import INT_MAX, CursorQuery, IdPath, LimitQuery

from app.schemas.playlists import (
    PlaylistCreate,
    PlaylistDetailOut,
    PlaylistMineOut,
    PlaylistOut,
    PlaylistUpdate,
    RandomVideoOut,
)
from app.schemas.videos import VideoPage

from app.services.playlists import PlaylistService

router = APIRouter(prefix="/api/playlists", tags=["playlists"])


# /mine объявлен раньше /{playlist_id}, иначе "mine" попадёт в параметр пути
@router.get("/mine", response_model=list[PlaylistMineOut])
async def my_playlists(
    user: CurrentUser,
    session: SessionDep,
    video_id: Annotated[int | None, Query(ge=1, le=INT_MAX)] = None,
):
    """Мои плейлисты. С video_id: в поле contains видно, лежит ли в них это видео."""
    return await PlaylistService(session).list_mine(user, video_id)

@router.get("/watch-later", response_model=PlaylistDetailOut)
async def watch_later(user: CurrentUser, session: SessionDep):
    """Мой плейлист «Смотреть позже» (создаётся при первом обращении)."""
    return await PlaylistService(session).watch_later(user)


@router.get("/liked", response_model=PlaylistOut)
async def liked_playlist(user: CurrentUser, session: SessionDep):
    """Мой плейлист «Понравившиеся» (создаётся при первом обращении)."""
    return await PlaylistService(session).liked(user)


@router.get("/liked/videos", response_model=VideoPage)
async def liked_videos(
    user: CurrentUser, session: SessionDep, cursor: CursorQuery = None, limit: LimitQuery = 24
):
    """Видео, которые я лайкнул: последние первыми. Закрытые от меня видео не показываются."""
    return await PlaylistService(session).liked_videos(user, cursor=cursor, limit=limit)


@router.post("", response_model=PlaylistOut, status_code=201)
async def create_playlist(data: PlaylistCreate, user: CurrentUser, session: SessionDep):
    return await PlaylistService(session).create(user, data)


@router.get("/{playlist_id}", response_model=PlaylistDetailOut)
async def get_playlist(playlist_id: IdPath, user: OptionalUser, session: SessionDep):
    return await PlaylistService(session).get(user, playlist_id)


@router.get("/{playlist_id}/random", response_model=RandomVideoOut)
async def random_video(playlist_id: IdPath, user: OptionalUser, session: SessionDep):
    """Случайное доступное видео плейлиста (video_id = null, если таких нет)."""
    return await PlaylistService(session).random(user, playlist_id)


@router.patch("/{playlist_id}", response_model=PlaylistOut)
async def update_playlist(
    playlist_id: IdPath, data: PlaylistUpdate, user: CurrentUser, session: SessionDep
):
    return await PlaylistService(session).update(user, playlist_id, data)


@router.delete("/{playlist_id}", status_code=204)
async def delete_playlist(playlist_id: IdPath, user: CurrentUser, session: SessionDep) -> None:
    await PlaylistService(session).delete(user, playlist_id)


@router.put("/{playlist_id}/items/{video_id}", status_code=204)
async def add_item(
    playlist_id: IdPath, video_id: IdPath, user: CurrentUser, session: SessionDep
) -> None:
    await PlaylistService(session).add_item(user, playlist_id, video_id)


@router.delete("/{playlist_id}/items/{video_id}", status_code=204)
async def remove_item(
    playlist_id: IdPath, video_id: IdPath, user: CurrentUser, session: SessionDep
) -> None:
    await PlaylistService(session).remove_item(user, playlist_id, video_id)