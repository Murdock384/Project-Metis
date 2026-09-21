from fastapi import APIRouter

from app.api.v1.endpoints import events, preferences, tasks, transport_events

api_router = APIRouter()
api_router.include_router(tasks.router)
api_router.include_router(events.router)
api_router.include_router(preferences.router)
api_router.include_router(transport_events.router)
