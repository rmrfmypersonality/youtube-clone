from app.models import Comment, User
from app.policies.roles import is_admin


def can_delete_comment(user: User | None, comment: Comment) -> bool:
    """Удалять чужое может только админ."""
    return user is not None and (comment.user_id == user.id or is_admin(user))