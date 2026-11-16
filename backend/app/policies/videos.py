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


def can_view_video(
    user: User | None,
    video: Video,
    *,
    is_shared: bool = False,
    channel_hidden: bool = False,
) -> bool:
    """is_shared: есть ли пользователь в video_shares (считает сервис, политика остаётся чистой).
    channel_hidden: владелец скрыл канал, тогда видео видит только он сам."""
    if is_owner(user, video):
        return True
    if channel_hidden:
        return False
    # Приватность проверяется раньше модерации: скрытие доступа к приватному не открывает
    if video.visibility == Visibility.private and not (user is not None and is_shared):
        return False
    if video.hidden_by_moderation and not can_moderate(user):
        return False
    return video.status == VideoStatus.ready