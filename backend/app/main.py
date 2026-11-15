from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError
from app.routers import auth, channels, comments, feed, playlists, reactions, system, videos

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