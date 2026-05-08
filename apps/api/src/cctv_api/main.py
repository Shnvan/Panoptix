from __future__ import annotations

from fastapi import FastAPI

from cctv_api.api.errors import ProblemDetail, problem_detail_handler
from cctv_api.api.health import router as health_router
from cctv_api.api.router import v1_router
from cctv_api.core.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    def override_settings() -> Settings:
        return resolved_settings

    application = FastAPI(
        title="Panoptix API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.APP_ENV == "development" else None,
        redoc_url=None,
    )

    application.add_exception_handler(ProblemDetail, problem_detail_handler)

    if settings is not None:
        application.dependency_overrides[get_settings] = override_settings

    application.include_router(health_router)
    application.include_router(v1_router)

    return application


app = create_app()
