import pytest

from app.models import Role, User
from app.policies import roles


@pytest.mark.parametrize(
    "role,moderate,admin",
    [
        (Role.user, False, False),
        (Role.moderator, True, False),
        (Role.admin, True, True),
    ],
)
def test_role_policies(role, moderate, admin):
    user = User(role=role)
    assert roles.can_moderate(user) is moderate
    assert roles.is_admin(user) is admin
    assert roles.can_manage_users(user) is admin


def test_anonymous_has_no_rights():
    assert roles.can_moderate(None) is False
    assert roles.is_admin(None) is False