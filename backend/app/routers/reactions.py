from fastapi import APIRouter

from app.core.deps import CurrentUser, SessionDep
from app.core.params import IdPath
from app.schemas.reactions import ReactionIn, ReactionOut
from app.services.reactions import ReactionService

router = APIRouter(prefix="/api/videos", tags=["reactions"])


@router.put("/{video_id}/reaction", response_model=ReactionOut)
async def set_reaction(video_id: IdPath, data: ReactionIn, user: CurrentUser, session: SessionDep):
    """value: 1 лайк, -1 дизлайк, 0 снять реакцию."""
    return await ReactionService(session).set(user, video_id, data.value)