from app.models import Role, User


def is_admin(user: User | None) -> bool:
    return user is not None and user.role == Role.admin


def can_moderate(user: User | None) -> bool:
    return user is not None and user.role in (Role.moderator, Role.admin)


def can_manage_users(user: User | None) -> bool:
    return is_admin(user)