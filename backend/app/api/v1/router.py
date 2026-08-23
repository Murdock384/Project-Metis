from fastapi import APIRouter

from app.api.v1.endpoints import events, tasks

api_router = APIRouter()
api_router.include_router(tasks.router)
api_router.include_router(events.router)
