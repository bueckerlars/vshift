from dataclasses import dataclass

from redis import Redis

from vshift.application.common.settings import QueueSettings, RedisConnectionSettings
from vshift.infrastructure.redis.client import create_redis_client
from vshift.infrastructure.redis.job_store import RedisJobRepository
from vshift.infrastructure.redis.keys import RedisKeys
from vshift.infrastructure.redis.processed_file_store import RedisProcessedFileStore
from vshift.infrastructure.redis.task_queue import RedisTaskQueue
from vshift.infrastructure.redis.worker_registry import RedisWorkerRegistry


@dataclass(frozen=True, slots=True)
class RedisStores:
    client: Redis
    keys: RedisKeys
    job_repository: RedisJobRepository
    task_queue: RedisTaskQueue
    processed_file_store: RedisProcessedFileStore
    worker_registry: RedisWorkerRegistry


def create_redis_stores(
    redis_settings: RedisConnectionSettings,
    queue_settings: QueueSettings,
) -> RedisStores:
    client = create_redis_client(redis_settings)
    keys = RedisKeys(prefix=queue_settings.key_prefix)
    return RedisStores(
        client=client,
        keys=keys,
        job_repository=RedisJobRepository(
            client,
            keys,
            ttl_seconds=queue_settings.ttl,
        ),
        task_queue=RedisTaskQueue(client, keys),
        processed_file_store=RedisProcessedFileStore(client, keys),
        worker_registry=RedisWorkerRegistry(
            client,
            keys,
            worker_ttl_seconds=queue_settings.worker_ttl_seconds,
            job_heartbeat_ttl_seconds=queue_settings.job_heartbeat_ttl_seconds,
        ),
    )
