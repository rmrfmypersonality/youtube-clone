from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.routers import (
    admin, auth, channels, comments, feed, moderation, playlists, reactions, reports, system, videos, subscriptions, account, categories, history,
)

app = FastAPI(title="YouTube Clone")


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(videos.router)
app.include_router(feed.router)
app.include_router(reactions.router)
app.include_router(comments.router)
app.include_router(channels.router)
app.include_router(playlists.router)
app.include_router(reports.router)
app.include_router(moderation.router)
app.include_router(admin.router)
app.include_router(subscriptions.router)
app.include_router(account.router)
app.include_router(categories.router)
app.include_router(history.router)