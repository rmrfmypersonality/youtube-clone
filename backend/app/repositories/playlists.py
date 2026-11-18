from sqlalchemy import and_, case, delete, false, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import (
    Channel,
    Like,
    Playlist,
    PlaylistItem,
    PlaylistKind,
    Video,
    VideoStatus,
    Visibility,
)
from app.models.playlist import LIKED_TITLE, WATCH_LATER_TITLE
from app.repositories.history import visible_to


def _visible(viewer_id: int | None):
    """Какие видео из плейлиста видит зритель: готовые и (публичные нескрытые или свои).
    Видео скрытых каналов чужие не видят."""
    # alias обязателен: без него подзапрос коррелирует с Channel внешнего запроса
    hidden_channel = aliased(Channel)
    hidden_owners = select(hidden_channel.owner_id).where(hidden_channel.is_hidden.is_(True))
    listed = and_(
        Video.visibility == Visibility.public,
        Video.hidden_by_moderation.is_(False),
        Video.owner_id.not_in(hidden_owners),
    )
    cond = listed if viewer_id is None else or_(listed, Video.owner_id == viewer_id)
    return and_(Video.status == VideoStatus.ready, cond)


def _summary_stmt(viewer_id: int | None, contains_video_id: int | None = None):
    vis = _visible(viewer_id)
    regular_count = (
        select(func.count())
        .select_from(PlaylistItem)
        .join(Video, Video.id == PlaylistItem.video_id)
        .where(PlaylistItem.playlist_id == Playlist.id, vis)
        .correlate(Playlist)
        .scalar_subquery()
    )
    regular_cover = (
        select(PlaylistItem.video_id)
        .select_from(PlaylistItem)
        .join(Video, Video.id == PlaylistItem.video_id)
        .where(PlaylistItem.playlist_id == Playlist.id, vis)
        .order_by(PlaylistItem.id)
        .limit(1)
        .correlate(Playlist)
        .scalar_subquery()
    )

    # «Понравившиеся»: содержимое из likes. Для не владельца плейлист всё равно недоступен (private),
    # id 0 просто даёт пустой результат.
    liked_channel = aliased(Channel)
    liked_where = and_(
        Like.user_id == Playlist.owner_id,
        Like.value == 1,
        visible_to(viewer_id if viewer_id is not None else 0, liked_channel),
    )
    liked_count = (
        select(func.count())
        .select_from(Like)
        .join(Video, Video.id == Like.video_id)
        .join(liked_channel, liked_channel.owner_id == Video.owner_id)
        .where(liked_where)
        .correlate(Playlist)
        .scalar_subquery()
    )
    liked_cover = (
        select(Like.video_id)
        .select_from(Like)
        .join(Video, Video.id == Like.video_id)
        .join(liked_channel, liked_channel.owner_id == Video.owner_id)
        .where(liked_where)
        .order_by(Like.id.desc())
        .limit(1)
        .correlate(Playlist)
        .scalar_subquery()
    )
    is_liked = Playlist.kind == PlaylistKind.liked
    items_count = case((is_liked, liked_count), else_=regular_count)
    cover = case((is_liked, liked_cover), else_=regular_cover)

    if contains_video_id is None:
        contains = false().label("contains")
    else:
        contains = (
            select(PlaylistItem.video_id)
            .where(
                PlaylistItem.playlist_id == Playlist.id,
                PlaylistItem.video_id == contains_video_id,
            )
            .correlate(Playlist)
            .exists()
            .label("contains")
        )
    return select(
        Playlist,
        Channel,
        items_count.label("items_count"),
        cover.label("cover_video_id"),
        contains,
    ).join(Channel, Channel.owner_id == Playlist.owner_id)


class PlaylistRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, playlist_id: int) -> Playlist | None:
        return await self.session.get(Playlist, playlist_id)

    def add(self, playlist: Playlist) -> None:
        self.session.add(playlist)

    async def count_by_owner(self, owner_id: int) -> int:
        """Лимит считает только обычные плейлисты, системные в него не входят."""
        stmt = (
            select(func.count())
            .select_from(Playlist)
            .where(Playlist.owner_id == owner_id, Playlist.kind == PlaylistKind.regular)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def count_items(self, playlist_id: int) -> int:
        stmt = select(func.count()).select_from(PlaylistItem).where(
            PlaylistItem.playlist_id == playlist_id
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def add_item(self, playlist_id: int, video_id: int) -> None:
        stmt = (
            insert(PlaylistItem)
            .values(playlist_id=playlist_id, video_id=video_id)
            .on_conflict_do_nothing()
        )
        await self.session.execute(stmt)

    async def remove_item(self, playlist_id: int, video_id: int) -> None:
        await self.session.execute(
            delete(PlaylistItem).where(
                PlaylistItem.playlist_id == playlist_id, PlaylistItem.video_id == video_id
            )
        )

    async def summary(self, playlist_id: int, viewer_id: int | None):
        stmt = _summary_stmt(viewer_id).where(Playlist.id == playlist_id)
        return (await self.session.execute(stmt)).first()

    async def list_summaries(
        self,
        *,
        owner_id: int,
        viewer_id: int | None,
        only_public: bool,
        contains_video_id: int | None = None,
        exclude_kinds: tuple[PlaylistKind, ...] = (),
        limit: int = 100,
    ):
        stmt = _summary_stmt(viewer_id, contains_video_id).where(Playlist.owner_id == owner_id)
        if only_public:
            stmt = stmt.where(Playlist.visibility == Visibility.public)
        if exclude_kinds:
            stmt = stmt.where(Playlist.kind.not_in(exclude_kinds))
        stmt = stmt.order_by(
            case(
                (Playlist.kind == PlaylistKind.watch_later, 0),
                (Playlist.kind == PlaylistKind.liked, 1),
                else_=2,
            ),
            Playlist.id.desc(),
        ).limit(limit)
        return (await self.session.execute(stmt)).all()

    async def list_items(
        self, playlist_id: int, viewer_id: int | None, limit: int
    ) -> list[tuple[Video, Channel]]:
        stmt = (
            select(Video, Channel)
            .select_from(PlaylistItem)
            .join(Video, Video.id == PlaylistItem.video_id)
            .join(Channel, Channel.owner_id == Video.owner_id)
            .where(PlaylistItem.playlist_id == playlist_id, _visible(viewer_id))
            .order_by(PlaylistItem.id)
            .limit(limit)
        )
        return [(r.Video, r.Channel) for r in (await self.session.execute(stmt)).all()]

    async def random_item(self, playlist_id: int, viewer_id: int | None) -> int | None:
        stmt = (
            select(Video.id)
            .select_from(PlaylistItem)
            .join(Video, Video.id == PlaylistItem.video_id)
            .where(PlaylistItem.playlist_id == playlist_id, _visible(viewer_id))
            .order_by(func.random())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _find_system(self, owner_id: int, kind: PlaylistKind) -> Playlist | None:
        stmt = select(Playlist).where(Playlist.owner_id == owner_id, Playlist.kind == kind)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _ensure_system(self, owner_id: int, kind: PlaylistKind, title: str) -> Playlist:
        """Возвращает системный плейлист, создаёт при первом обращении. Коммитит вызывающий."""
        existing = await self._find_system(owner_id, kind)
        if existing is not None:
            return existing
        # DO NOTHING: параллельный запрос мог успеть раньше, уникальный индекс не даст создать второй
        await self.session.execute(
            insert(Playlist)
            .values(
                owner_id=owner_id,
                title=title,
                description="",
                visibility=Visibility.private,
                kind=kind,
            )
            .on_conflict_do_nothing()
        )
        found = await self._find_system(owner_id, kind)
        assert found is not None
        return found

    async def ensure_watch_later(self, owner_id: int) -> Playlist:
        return await self._ensure_system(owner_id, PlaylistKind.watch_later, WATCH_LATER_TITLE)

    async def ensure_liked(self, owner_id: int) -> Playlist:
        return await self._ensure_system(owner_id, PlaylistKind.liked, LIKED_TITLE)