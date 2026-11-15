from typing import Annotated

from fastapi import APIRouter, Path

from app.core.deps import CurrentUser, OptionalUser, SessionDep
from app.core.params import CursorQuery, LimitQuery
from app.schemas.auth import USERNAME_RE
from app.schemas.channels import ChannelOut, ChannelUpdate, SubscriptionOut
from app.schemas.playlists import PlaylistOut
from app.schemas.videos import VideoPage
from app.services.channels import ChannelService
from app.services.playlists import PlaylistService

router = APIRouter(prefix="/api/channels", tags=["channels"])

Handle = Annotated[str, Path(pattern=USERNAME_RE)]


@router.patch("/me", response_model=ChannelOut)
async def update_my_channel(data: ChannelUpdate, user: CurrentUser, session: SessionDep):
    return await ChannelService(session).update_mine(user, data)


@router.get("/{handle}", response_model=ChannelOut)
async def get_channel(handle: Handle, user: OptionalUser, session: SessionDep):
    return await ChannelService(session).get(user, handle)


@router.get("/{handle}/videos", response_model=VideoPage)
async def channel_videos(
    handle: Handle, session: SessionDep, cursor: CursorQuery = None, limit: LimitQuery = 24
):
    return await ChannelService(session).list_videos(handle, cursor=cursor, limit=limit)


@router.get("/{handle}/playlists", response_model=list[PlaylistOut])
async def channel_playlists(handle: Handle, user: OptionalUser, session: SessionDep):
    return await PlaylistService(session).list_for_channel(user, handle)


@router.put("/{handle}/subscription", response_model=SubscriptionOut)
async def subscribe(handle: Handle, user: CurrentUser, session: SessionDep):
    return await ChannelService(session).subscribe(user, handle)


@router.delete("/{handle}/subscription", response_model=SubscriptionOut)
async def unsubscribe(handle: Handle, user: CurrentUser, session: SessionDep):
    return await ChannelService(session).unsubscribe(user, handle)