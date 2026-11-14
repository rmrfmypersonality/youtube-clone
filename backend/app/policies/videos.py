from app.models import User, Video, VideoStatus, Visibility
from app.policies.roles import can_moderate, is_admin


def is_owner(user: User | None, video: Video) -> bool:
    return user is not None and video.owner_id == user.id


def can_edit_video(user: User | None, video: Video) -> bool:
    """Редактировать и удалять чужое может только админ."""
    return is_owner(user, video) or is_admin(user)


def can_upload_video_file(user: User | None, video: Video) -> bool:
    return is_owner(user, video)


def can_manage_shares(user: User | None, video: Video) -> bool:
    return is_owner(user, video)


def can_view_video(user: User | None, video: Video, *, is_shared: bool = False) -> bool:
    """is_shared: есть ли пользователь в video_shares (считает сервис, политика остаётся чистой)."""
    if is_owner(user, video):
        return True
    if video.hidden_by_moderation:
        return can_moderate(user)
    if video.status != VideoStatus.ready:
        return False
    if video.visibility in (Visibility.public, Visibility.unlisted):
        return True
    return user is not None and is_shared