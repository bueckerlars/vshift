from typing import Annotated

from fastapi import Depends, Request
from redis import Redis

from vshift.application.server.application_context import ServerApplicationContext
from vshift.ports.job_repository import JobRepository


def get_context(request: Request) -> ServerApplicationContext:
    context = request.app.state.context
    if not isinstance(context, ServerApplicationContext):
        msg = "application context is not configured"
        raise RuntimeError(msg)
    return context


ServerApplicationContextDep = Annotated[
    ServerApplicationContext,
    Depends(get_context),
]


def get_redis_client(context: ServerApplicationContextDep) -> Redis:
    return context.redis_stores.client


def get_job_repository(context: ServerApplicationContextDep) -> JobRepository:
    return context.redis_stores.job_repository


RedisClientDep = Annotated[Redis, Depends(get_redis_client)]
JobRepositoryDep = Annotated[JobRepository, Depends(get_job_repository)]
