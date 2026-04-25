from fastapi import APIRouter, Depends

from app.schemas.common import HealthResponse
from app.services.container import ServiceContainer, get_container

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health(container: ServiceContainer = Depends(get_container)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        environment=container.settings.app_env,
        search_backend=container.search_backend.backend_name,
        workflow_mode=container.orchestrator.mode,
    )

