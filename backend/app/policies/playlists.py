from app.models import Playlist, User, Video, Visibility, PlaylistKind
from app.policies.roles import is_admin


def is_owner(user: User | None, playlist: Playlist) -> bool:
    return user is not None and playlist.owner_id == user.id


def can_view_playlist(user: User | None, playlist: Playlist) -> bool:
    """public и unlisted открываются любому по ссылке, private только владельцу."""
    return playlist.visibility != Visibility.private or is_owner(user, playlist)


def can_edit_playlist(user: User | None, playlist: Playlist) -> bool:
    """Править и удалять чужое может только админ."""
    return is_owner(user, playlist) or is_admin(user)


def can_modify_items(user: User | None, playlist: Playlist) -> bool:
    return is_owner(user, playlist)


def can_add_video(user: User, video: Video) -> bool:
    """В плейлист можно класть свои видео и чужие публичные."""
    if video.owner_id == user.id:
        return True
    return video.visibility == Visibility.public and not video.hidden_by_moderation

def is_system(playlist: Playlist) -> bool:
    """Системный плейлист («Смотреть позже»): нельзя менять и удалять никому."""
    return playlist.kind != PlaylistKind.regular