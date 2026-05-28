from fastapi import APIRouter

from app.api.v1.endpoints import health
from app.api.v1.endpoints import auth
from app.api.v1.endpoints import assistant

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(assistant.router)
