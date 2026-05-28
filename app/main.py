from fastapi import FastAPI

from app.api.v1.middleware import auth_middleware
from app.api.v1.router import api_router
from app.core.config import settings


def create_app() -> FastAPI:
    application = FastAPI(title=settings.PROJECT_NAME, debug=settings.DEBUG)
    application.middleware("http")(auth_middleware)
    application.include_router(api_router, prefix=settings.API_V1_PREFIX)
    return application


app = create_app()
