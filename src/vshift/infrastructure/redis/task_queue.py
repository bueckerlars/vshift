from uuid import UUID

from redis import Redis

from vshift.infrastructure.redis.keys import RedisKeys


class RedisTaskQueue:
    """Redis LIST-backed FIFO task queue."""

    def __init__(self, client: Redis, keys: RedisKeys) -> None:
        self._client = client
        self._keys = keys

    def enqueue(self, job_id: UUID) -> None:
        self._client.lpush(self._keys.pending_queue, str(job_id))

    def dequeue(self, *, timeout_seconds: int = 0) -> UUID | None:
        if timeout_seconds > 0:
            result = self._client.brpop(
                self._keys.pending_queue,
                timeout=timeout_seconds,
            )
            if result is None:
                return None
            _, raw_job_id = result
            return UUID(str(raw_job_id))

        raw_job_id = self._client.rpop(self._keys.pending_queue)
        if raw_job_id is None:
            return None
        return UUID(str(raw_job_id))

    def requeue(self, job_id: UUID) -> None:
        self._client.rpush(self._keys.pending_queue, str(job_id))

    def depth(self) -> int:
        return int(self._client.llen(self._keys.pending_queue))

    def push_to_dead_letter(self, job_id: UUID) -> None:
        self._client.lpush(self._keys.dead_letter_queue, str(job_id))

    def dead_letter_depth(self) -> int:
        return int(self._client.llen(self._keys.dead_letter_queue))
