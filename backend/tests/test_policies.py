import pytest

from app.models import Role, User
from app.policies import roles
from app.models import Video  # noqa: E402
from app.policies import videos as video_policy  # noqa: E402


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


def test_video_edit_policy():
    video = Video(owner_id=1)
    assert video_policy.can_edit_video(User(id=1, role=Role.user), video)
    assert not video_policy.can_edit_video(User(id=2, role=Role.user), video)
    assert not video_policy.can_edit_video(User(id=3, role=Role.moderator), video)
    assert video_policy.can_edit_video(User(id=4, role=Role.admin), video)
    assert not video_policy.can_edit_video(None, video)


def test_only_owner_uploads_file():
    video = Video(owner_id=1)
    assert video_policy.can_upload_video_file(User(id=1, role=Role.user), video)
    assert not video_policy.can_upload_video_file(User(id=4, role=Role.admin), video)