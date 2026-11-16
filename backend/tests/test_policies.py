import pytest

from app.models import Role, User, Video, VideoStatus, Visibility, Comment, Playlist
from app.policies import roles
from app.policies import videos as video_policy
from app.policies import comments as comment_policy  # noqa: E402
from app.policies import playlists as playlist_policy  # noqa: E402
from app.policies import reports as report_policy  # noqa: E402


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


def test_comment_delete_policy():
    comment = Comment(user_id=1)
    assert comment_policy.can_delete_comment(OWNER, comment)
    assert comment_policy.can_delete_comment(ADMIN, comment)
    assert not comment_policy.can_delete_comment(STRANGER, comment)
    assert not comment_policy.can_delete_comment(MODERATOR, comment)
    assert not comment_policy.can_delete_comment(None, comment)


def test_playlist_policies():
    public, private = Playlist(owner_id=1, is_public=True), Playlist(owner_id=1, is_public=False)
    assert playlist_policy.can_view_playlist(None, public)
    assert playlist_policy.can_view_playlist(OWNER, private)
    for viewer in (None, STRANGER, MODERATOR, ADMIN):
        assert not playlist_policy.can_view_playlist(viewer, private)

    assert playlist_policy.can_edit_playlist(OWNER, public)
    assert playlist_policy.can_edit_playlist(ADMIN, public)
    assert not playlist_policy.can_edit_playlist(STRANGER, public)
    assert not playlist_policy.can_edit_playlist(MODERATOR, public)

    assert playlist_policy.can_modify_items(OWNER, public)
    assert not playlist_policy.can_modify_items(ADMIN, public)  # админ может удалить, но не наполнять


def test_can_add_video_to_playlist():
    own = Video(owner_id=1, visibility=Visibility.private)
    assert playlist_policy.can_add_video(OWNER, own)
    assert playlist_policy.can_add_video(STRANGER, _video(Visibility.public))
    assert not playlist_policy.can_add_video(STRANGER, _video(Visibility.unlisted))
    assert not playlist_policy.can_add_video(STRANGER, _video(Visibility.private))
    assert not playlist_policy.can_add_video(STRANGER, _video(Visibility.public, hidden=True))

def test_moderator_cannot_view_hidden_private_video():
    video = _video(Visibility.private, hidden=True)
    for viewer in (None, STRANGER, MODERATOR, ADMIN):
        assert not video_policy.can_view_video(viewer, video)
    assert video_policy.can_view_video(OWNER, video)
    assert video_policy.can_view_video(MODERATOR, video, is_shared=True)
    assert not video_policy.can_view_video(STRANGER, video, is_shared=True)


def test_comment_view_policy():
    visible = Comment(user_id=1, hidden_by_moderation=False)
    hidden = Comment(user_id=1, hidden_by_moderation=True)
    for viewer in (None, OWNER, STRANGER, MODERATOR, ADMIN):
        assert comment_policy.can_view_comment(viewer, visible)
    for viewer in (OWNER, MODERATOR, ADMIN):
        assert comment_policy.can_view_comment(viewer, hidden)
    for viewer in (None, STRANGER):
        assert not comment_policy.can_view_comment(viewer, hidden)


def test_report_policies():
    assert report_policy.can_report_video(STRANGER, _video())
    assert not report_policy.can_report_video(OWNER, _video())
    assert report_policy.can_report_comment(STRANGER, Comment(user_id=1))
    assert not report_policy.can_report_comment(OWNER, Comment(user_id=1))


def test_can_change_user_policy():
    assert roles.can_change_user(ADMIN, STRANGER)
    assert roles.can_change_user(ADMIN, MODERATOR)
    assert not roles.can_change_user(ADMIN, ADMIN)  # себя нельзя
    assert not roles.can_change_user(MODERATOR, STRANGER)
    assert not roles.can_change_user(STRANGER, STRANGER)
    assert not roles.can_change_user(None, STRANGER)


def test_hidden_channel_blocks_everyone_but_owner():
    video = _video()
    assert video_policy.can_view_video(OWNER, video, channel_hidden=True)
    for viewer in (None, STRANGER, MODERATOR, ADMIN):
        assert not video_policy.can_view_video(viewer, video, channel_hidden=True)
    shared_private = _video(Visibility.private)
    assert not video_policy.can_view_video(STRANGER, shared_private, is_shared=True, channel_hidden=True)