from app.models import Comment, User
from app.policies.roles import can_moderate, is_admin


def can_delete_comment(user: User | None, comment: Comment) -> bool:
    """Удалять чужое может только админ."""
    return user is not None and (comment.user_id == user.id or is_admin(user))


def can_view_comment(user: User | None, comment: Comment) -> bool:
    """Скрытый модерацией комментарий видят автор и модераторы."""
    if not comment.hidden_by_moderation:
        return True
    return can_moderate(user) or (user is not None and comment.user_id == user.id)