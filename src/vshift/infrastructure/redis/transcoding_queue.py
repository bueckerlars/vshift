from redis import Redis

from vshift.application.common.settings import RedisConnectionSettings


class TranscodingQueue:
    """Transcoding queue is used to store the transcoding tasks."""

    def __init__(self, redis_settings: RedisConnectionSettings) -> None:
        self._redis_settings = redis_settings
        self._redis_client = Redis(
            host=redis_settings.host,
            port=redis_settings.port,
            password=redis_settings.password.get_secret_value(),
            db=redis_settings.database,
        )
