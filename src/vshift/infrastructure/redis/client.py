from redis import Redis

from vshift.application.common.settings import RedisConnectionSettings


def create_redis_client(settings: RedisConnectionSettings) -> Redis:
    return Redis(
        host=settings.host,
        port=settings.port,
        password=settings.password.get_secret_value(),
        db=settings.database,
        decode_responses=True,
    )
