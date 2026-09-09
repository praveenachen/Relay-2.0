from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from starlette.responses import Response

from app.api.health import router as health_router
from app.api.routes import router
from app.auth.users import UserCreate, UserRead, backend, users
from app.core.config import get_settings
from app.domain.errors import DomainError


def create_app() -> FastAPI:
    application = FastAPI(title="Relay API", version="0.2.0")

    @application.middleware("http")
    async def secure_requests(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            # Strict browser Origin validation also covers login CSRF. No wildcard CORS.
            if request.headers.get("origin") != get_settings().frontend_origin:
                return JSONResponse(
                    status_code=403,
                    content={
                        "code": "ORIGIN_REJECTED",
                        "message": "Request origin is not allowed.",
                    },
                )
        response = await call_next(request)
        if request.url.path != "/health":
            response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    @application.exception_handler(DomainError)
    async def domain_error(request: Request, error: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=error.status_code, content={"code": error.code, "message": error.message}
        )

    @application.exception_handler(RequestValidationError)
    async def invalid_request(request: Request, error: RequestValidationError) -> JSONResponse:
        # Never echo submitted passwords, credentials, or arbitrary payloads in validation errors.
        return JSONResponse(
            status_code=422,
            content={
                "code": "VALIDATION_ERROR",
                "message": "Check the submitted fields and try again.",
                "fields": [".".join(str(p) for p in e["loc"]) for e in error.errors()],
            },
        )

    @application.exception_handler(IntegrityError)
    async def conflict(request: Request, error: IntegrityError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"code": "CONFLICT", "message": "The change conflicts with existing data."},
        )

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, error: SQLAlchemyError) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "code": "DATABASE_UNAVAILABLE",
                "message": "Relay storage is unavailable. Please try again later.",
            },
        )

    application.include_router(health_router)
    application.include_router(
        users.get_register_router(UserRead, UserCreate), prefix="/auth", tags=["authentication"]
    )
    application.include_router(
        users.get_auth_router(backend), prefix="/auth", tags=["authentication"]
    )
    application.include_router(router)
    return application


app = create_app()
