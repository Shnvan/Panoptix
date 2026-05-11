from __future__ import annotations

import asyncio

from fastapi import FastAPI

from cctv_api.api.errors import ProblemDetail, problem_detail_handler
from cctv_api.api.health import router as health_router
from cctv_api.api.router import v1_router
from cctv_api.core.config import Settings, get_settings
from cctv_api.db import get_sessionmaker
from cctv_api.gateway.command_queue import create_ack_sink, create_command_provider
from cctv_api.jobs.maintenance import maintenance_scheduler_loop, should_start_maintenance_scheduler
from cctv_api.security.headers import add_security_headers


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_settings.validate_production_guardrails()

    def override_settings() -> Settings:
        return resolved_settings

    application = FastAPI(
        title="Panoptix API",
        version="0.1.0",
        docs_url="/docs" if resolved_settings.APP_ENV == "development" else None,
        redoc_url=None,
    )

    application.add_exception_handler(ProblemDetail, problem_detail_handler)
    application.middleware("http")(lambda request, call_next: add_security_headers(request, call_next, resolved_settings))
    application.router.add_event_handler("startup", _scheduler_startup(application, resolved_settings))
    application.router.add_event_handler("shutdown", _scheduler_shutdown(application))

    if settings is not None:
        application.dependency_overrides[get_settings] = override_settings

    application.include_router(health_router)
    application.include_router(v1_router)

    if "replace-me" not in resolved_settings.DATABASE_URL:
        application.state.gateway_control_command_provider = create_command_provider()
        application.state.gateway_control_ack_sink = create_ack_sink()

    return application


def _scheduler_startup(application: FastAPI, settings: Settings):
    async def _startup() -> None:
        if should_start_maintenance_scheduler(settings):
            task = asyncio.create_task(maintenance_scheduler_loop(get_sessionmaker(), settings=settings))
            application.state.maintenance_scheduler_task = task
        else:
            application.state.maintenance_scheduler_task = None

    return _startup


def _scheduler_shutdown(application: FastAPI):
    async def _shutdown() -> None:
        task = getattr(application.state, "maintenance_scheduler_task", None)
        if task is None:
            return
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    return _shutdown


app = create_app()
