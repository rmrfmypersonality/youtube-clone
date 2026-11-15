from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, Conflict, NotFound
from app.models import Playlist, User, VideoStatus
from app.policies import playlists as policy
from app.repositories.channels import ChannelRepository
from app.repositories.playlists import PlaylistRepository
from app.repositories.audit import AuditRepository
from app.schemas.auth import ChannelBrief
from app.schemas.playlists import (
    PlaylistCreate,
    PlaylistDetailOut,
    PlaylistMineOut,
    PlaylistOut,
    PlaylistUpdate,
)
from app.services.feed import to_card
from app.services.video_access import VideoAccess

MAX_PLAYLISTS = 100
MAX_ITEMS = 200
NOT_FOUND = "Плейлист не найден"


def _out(row, cls=PlaylistOut, **extra):
    p = row.Playlist
    return cls(
        id=p.id,
        title=p.title,
        description=p.description,
        is_public=p.is_public,
        created_at=p.created_at,
        items_count=row.items_count,
        cover_video_id=row.cover_video_id,
        channel=ChannelBrief.model_validate(row.Channel),
        **extra,
    )


class PlaylistService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.playlists = PlaylistRepository(session)
        self.channels = ChannelRepository(session)
        self.access = VideoAccess(session)
        self.audit = AuditRepository(session)

    async def _viewable(self, user: User | None, playlist_id: int) -> Playlist:
        playlist = await self.playlists.get(playlist_id)
        if playlist is None or not policy.can_view_playlist(user, playlist):
            raise NotFound(NOT_FOUND)
        return playlist

    async def _editable(self, user: User, playlist_id: int) -> Playlist:
        playlist = await self.playlists.get(playlist_id)
        if playlist is None or not policy.can_edit_playlist(user, playlist):
            raise NotFound(NOT_FOUND)
        return playlist

    async def _out_for(self, playlist_id: int, user: User) -> PlaylistOut:
        return _out(await self.playlists.summary(playlist_id, user.id))

    async def create(self, user: User, data: PlaylistCreate) -> PlaylistOut:
        if await self.playlists.count_by_owner(user.id) >= MAX_PLAYLISTS:
            raise Conflict("Достигнут лимит плейлистов")
        playlist = Playlist(
            owner_id=user.id,
            title=data.title,
            description=data.description,
            is_public=data.is_public,
        )
        self.playlists.add(playlist)
        await self.session.commit()
        return await self._out_for(playlist.id, user)

    async def get(self, user: User | None, playlist_id: int) -> PlaylistDetailOut:
        playlist = await self._viewable(user, playlist_id)
        viewer_id = user.id if user else None
        row = await self.playlists.summary(playlist.id, viewer_id)
        rows = await self.playlists.list_items(playlist.id, viewer_id, MAX_ITEMS)
        return _out(
            row,
            PlaylistDetailOut,
            items=[to_card(v, ch) for v, ch in rows],
            is_owner=policy.is_owner(user, playlist),
        )

    async def update(self, user: User, playlist_id: int, data: PlaylistUpdate) -> PlaylistOut:
        playlist = await self._editable(user, playlist_id)
        if not policy.is_owner(user, playlist):  # действие админа над чужим
            self.audit.log(
                user, "playlist.update", "playlist", playlist.id,
                {"owner_id": playlist.owner_id, "title": playlist.title},
            )
        if data.title is not None:
            playlist.title = data.title
        if data.description is not None:
            playlist.description = data.description
        if data.is_public is not None:
            playlist.is_public = data.is_public
        await self.session.commit()
        return await self._out_for(playlist.id, user)

    async def delete(self, user: User, playlist_id: int) -> None:
        playlist = await self._editable(user, playlist_id)
        if not policy.is_owner(user, playlist):  # действие админа над чужим
            self.audit.log(
                user, "playlist.delete", "playlist", playlist.id,
                {"owner_id": playlist.owner_id, "title": playlist.title},
            )
        await self.session.delete(playlist)  # элементы удалит каскад в БД
        await self.session.commit()

    async def add_item(self, user: User, playlist_id: int, video_id: int) -> None:
        playlist = await self.playlists.get(playlist_id)
        if playlist is None or not policy.can_modify_items(user, playlist):
            raise NotFound(NOT_FOUND)
        video, _ = await self.access.visible(user, video_id)
        if video.status != VideoStatus.ready:
            raise Conflict("Видео ещё не готово")
        if not policy.can_add_video(user, video):
            raise AppError("Это видео нельзя добавить в плейлист")
        if await self.playlists.count_items(playlist.id) >= MAX_ITEMS:
            raise Conflict("В плейлисте слишком много видео")
        await self.playlists.add_item(playlist.id, video.id)
        await self.session.commit()

    async def remove_item(self, user: User, playlist_id: int, video_id: int) -> None:
        playlist = await self.playlists.get(playlist_id)
        if playlist is None or not policy.can_modify_items(user, playlist):
            raise NotFound(NOT_FOUND)
        await self.playlists.remove_item(playlist.id, video_id)
        await self.session.commit()

    async def list_for_channel(self, viewer: User | None, handle: str) -> list[PlaylistOut]:
        channel = await self.channels.get_by_handle(handle)
        if channel is None:
            raise NotFound("Канал не найден")
        is_owner = viewer is not None and viewer.id == channel.owner_id
        rows = await self.playlists.list_summaries(
            owner_id=channel.owner_id,
            viewer_id=viewer.id if viewer else None,
            only_public=not is_owner,
        )
        return [_out(r) for r in rows]

    async def list_mine(self, user: User, video_id: int | None) -> list[PlaylistMineOut]:
        rows = await self.playlists.list_summaries(
            owner_id=user.id, viewer_id=user.id, only_public=False, contains_video_id=video_id
        )
        return [_out(r, PlaylistMineOut, contains=bool(r.contains)) for r in rows]