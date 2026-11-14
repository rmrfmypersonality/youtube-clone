import pytest

from app.models import Role, User, Video, VideoStatus, Visibility
from app.policies import roles
from app.policies import videos as video_policy


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


OWNER = User(id=1, role=Role.user)
STRANGER = User(id=2, role=Role.user)
MODERATOR = User(id=3, role=Role.moderator)
ADMIN = User(id=4, role=Role.admin)


def _video(visibility=Visibility.public, status=VideoStatus.ready, hidden=False):
    return Video(owner_id=1, visibility=visibility, status=status, hidden_by_moderation=hidden)


def test_view_public_and_unlisted():
    for visibility in (Visibility.public, Visibility.unlisted):
        video = _video(visibility)
        for viewer in (None, OWNER, STRANGER, MODERATOR, ADMIN):
            assert video_policy.can_view_video(viewer, video)


def test_view_private():
    video = _video(Visibility.private)
    assert video_policy.can_view_video(OWNER, video)
    assert video_policy.can_view_video(STRANGER, video, is_shared=True)
    assert not video_policy.can_view_video(STRANGER, video)
    assert not video_policy.can_view_video(None, video, is_shared=True)
    # модератор и админ приватное не видят
    assert not video_policy.can_view_video(MODERATOR, video)
    assert not video_policy.can_view_video(ADMIN, video)


def test_view_hidden_by_moderation():
    video = _video(hidden=True)
    assert video_policy.can_view_video(OWNER, video)
    assert video_policy.can_view_video(MODERATOR, video)
    assert video_policy.can_view_video(ADMIN, video)
    assert not video_policy.can_view_video(STRANGER, video)
    assert not video_policy.can_view_video(None, video)
    # доступ по shares скрытое не открывает
    assert not video_policy.can_view_video(STRANGER, _video(Visibility.private, hidden=True), is_shared=True)


def test_view_unfinished_only_owner():
    video = _video(status=VideoStatus.processing)
    assert video_policy.can_view_video(OWNER, video)
    for viewer in (None, STRANGER, MODERATOR, ADMIN):
        assert not video_policy.can_view_video(viewer, video)


def test_manage_shares_owner_only():
    video = _video()
    assert video_policy.can_manage_shares(OWNER, video)
    for viewer in (None, STRANGER, MODERATOR, ADMIN):
        assert not video_policy.can_manage_shares(viewer, video)