from typing import Literal

from fastapi import APIRouter

from app.core.deps import CurrentUser, OptionalUser, SessionDep
from app.core.params import CursorQuery, IdPath, LimitQuery
from app.schemas.comments import CommentCreate, CommentOut, CommentPage
from app.services.comments import CommentService

router = APIRouter(prefix="/api", tags=["comments"])


@router.get("/videos/{video_id}/comments", response_model=CommentPage)
async def list_comments(
    video_id: IdPath,
    user: OptionalUser,
    session: SessionDep,
    sort: Literal["new", "old"] = "new",
    cursor: CursorQuery = None,
    limit: LimitQuery = 20,
):
    return await CommentService(session).list_for_video(
        user, video_id, sort=sort, cursor=cursor, limit=limit
    )


@router.post("/videos/{video_id}/comments", response_model=CommentOut, status_code=201)
async def create_comment(
    video_id: IdPath, data: CommentCreate, user: CurrentUser, session: SessionDep
):
    return await CommentService(session).create(user, video_id, data)


@router.get("/comments/{comment_id}/replies", response_model=CommentPage)
async def list_replies(
    comment_id: IdPath,
    user: OptionalUser,
    session: SessionDep,
    cursor: CursorQuery = None,
    limit: LimitQuery = 20,
):
    return await CommentService(session).list_replies(user, comment_id, cursor=cursor, limit=limit)


@router.delete("/comments/{comment_id}", status_code=204)
async def delete_comment(comment_id: IdPath, user: CurrentUser, session: SessionDep) -> None:
    await CommentService(session).delete(user, comment_id)