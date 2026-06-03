from datetime import UTC, datetime
from uuid import UUID

from redis import Redis

from vshift.domain.worker.worker_info import WorkerInfo
from vshift.infrastructure.redis.keys import RedisKeys


class RedisWorkerRegistry:
    """Redis-backed worker registration and job heartbeats."""

    def __init__(
        self,
        client: Redis,
        keys: RedisKeys,
        *,
        worker_ttl_seconds: int,
        job_heartbeat_ttl_seconds: int,
    ) -> None:
        self._client = client
        self._keys = keys
        self._worker_ttl_seconds = worker_ttl_seconds
        self._job_heartbeat_ttl_seconds = job_heartbeat_ttl_seconds

    def register(self, worker: WorkerInfo) -> None:
        worker_key = self._keys.worker(worker.worker_id)
        self._client.set(
            worker_key,
            worker.model_dump_json(),
            ex=self._worker_ttl_seconds,
        )
        self._client.sadd(self._keys.workers_index, str(worker.worker_id))

    def heartbeat(self, worker_id: UUID) -> None:
        worker_key = self._keys.worker(worker_id)
        payload = self._client.get(worker_key)
        if payload is None:
            return

        worker = WorkerInfo.model_validate_json(payload)
        refreshed = worker.model_copy(
            update={"last_seen_at": datetime.now(tz=UTC)},
        )
        self._client.set(
            worker_key,
            refreshed.model_dump_json(),
            ex=self._worker_ttl_seconds,
        )

    def deregister(self, worker_id: UUID) -> None:
        self._client.delete(self._keys.worker(worker_id))
        self._client.srem(self._keys.workers_index, str(worker_id))

    def list_workers(self) -> list[WorkerInfo]:
        worker_ids = self._client.smembers(self._keys.workers_index)
        workers: list[WorkerInfo] = []
        for worker_id in worker_ids:
            payload = self._client.get(self._keys.worker(UUID(str(worker_id))))
            if payload is None:
                self._client.srem(self._keys.workers_index, worker_id)
                continue
            workers.append(WorkerInfo.model_validate_json(payload))
        return workers

    def set_job_heartbeat(self, job_id: UUID, worker_id: UUID) -> None:
        self._client.set(
            self._keys.job_heartbeat(job_id),
            str(worker_id),
            ex=self._job_heartbeat_ttl_seconds,
        )

    def is_job_alive(self, job_id: UUID) -> bool:
        return self._client.exists(self._keys.job_heartbeat(job_id)) > 0
