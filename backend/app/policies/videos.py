from app.models import User, Video
from app.policies.roles import is_admin


def is_owner(user: User | None, video: Video) -> bool:
    return user is not None and video.owner_id == user.id


def can_edit_video(user: User | None, video: Video) -> bool:
    """Редактировать и удалять чужое может только админ."""
    return is_owner(user, video) or is_admin(user)


def can_upload_video_file(user: User | None, video: Video) -> bool:
    return is_owner(user, video)