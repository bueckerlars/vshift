from fastapi import APIRouter
from redis import Redis
from redis.exceptions import RedisError

from vshift import __version__
from vshift.infrastructure.api.dependencies import RedisClientDep
from vshift.infrastructure.api.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Reports service status and Redis connectivity.",
)
def health(redis_client: RedisClientDep) -> HealthResponse:
    redis_status = _check_redis(redis_client)
    status = "ok" if redis_status == "ok" else "degraded"
    return HealthResponse(status=status, redis=redis_status, version=__version__)


def _check_redis(redis_client: Redis) -> str:
    try:
        redis_client.ping()  # pyright: ignore[reportUnknownMemberType]
    except RedisError:
        return "error"
    return "ok"
