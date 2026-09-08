from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Process liveness only; does not imply database or integration readiness."""
    return HealthResponse(status="ok", service="relay-api")
