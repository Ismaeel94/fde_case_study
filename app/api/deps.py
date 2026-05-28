from typing import Annotated

from fastapi import Depends

from app.services.health import HealthService, health_service


def get_health_service() -> HealthService:
    return health_service


HealthServiceDep = Annotated[HealthService, Depends(get_health_service)]
