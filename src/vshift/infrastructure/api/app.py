from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from threading import Event, Thread

from fastapi import FastAPI

from vshift.application.server.application_context import ServerApplicationContext
from vshift.infrastructure.api.background import start_background_threads
from vshift.infrastructure.api.openapi import (
    API_DESCRIPTION,
    API_TITLE,
    API_VERSION,
    OPENAPI_TAGS,
)
from vshift.infrastructure.api.routers import health_router, jobs_router


def create_app(
    context: ServerApplicationContext,
    *,
    background_tasks: bool = True,
) -> FastAPI:
    stop_event = Event()
    threads: list[Thread] = []
    api_settings = context.settings.api

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        if background_tasks:
            threads.extend(start_background_threads(context, stop_event))
        yield
        if background_tasks:
            stop_event.set()
            for thread in threads:
                thread.join(timeout=5)

    docs_url = api_settings.docs_url if api_settings.docs_enabled else None
    redoc_url = api_settings.redoc_url if api_settings.docs_enabled else None
    openapi_url = api_settings.openapi_url if api_settings.docs_enabled else None

    app = FastAPI(
        title=API_TITLE,
        version=API_VERSION,
        description=API_DESCRIPTION,
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        docs_url=docs_url,
        redoc_url=redoc_url,
        openapi_url=openapi_url,
    )
    app.state.context = context
    app.include_router(health_router)
    app.include_router(jobs_router)
    return app
