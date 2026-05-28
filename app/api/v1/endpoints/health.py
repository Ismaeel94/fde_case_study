from fastapi import APIRouter

from app.api.deps import HealthServiceDep
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health_check(service: HealthServiceDep) -> HealthResponse:
    return service.get_status()
