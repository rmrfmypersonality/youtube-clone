from app.models import Comment, User, Video


def can_report_video(user: User, video: Video) -> bool:
    return video.owner_id != user.id


def can_report_comment(user: User, comment: Comment) -> bool:
    return comment.user_id != user.id