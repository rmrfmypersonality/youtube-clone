from fastapi import FastAPI

from app.routers import system

app = FastAPI(title="YouTube Clone")

app.include_router(system.router)