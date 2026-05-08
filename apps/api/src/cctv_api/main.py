from __future__ import annotations

from fastapi import FastAPI

from cctv_api.api.errors import ProblemDetail, problem_detail_handler
from cctv_api.api.health import router as health_router
from cctv_api.api.router import v1_router
from cctv_api.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    application = FastAPI(
        title="Panoptix API",
        version="0.1.0",
        docs_url="/docs" if settings.APP_ENV == "development" else None,
        redoc_url=None,
    )

    application.add_exception_handler(ProblemDetail, problem_detail_handler)

    application.include_router(health_router)
    application.include_router(v1_router)

    return application


app = create_app()
