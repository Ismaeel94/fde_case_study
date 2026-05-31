from typing import Annotated

from fastapi import Depends

from app.services import assistant as assistant_module
from app.services.health import HealthService, health_service
from langchain_openai import ChatOpenAI
from app.core.config import settings


def get_health_service() -> HealthService:
    return health_service


def get_assistant_service() -> assistant_module.AssistantService:
    return assistant_module.assistant_service


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
