from uuid import UUID

from redis import Redis

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.infrastructure.redis.keys import RedisKeys


class RedisJobRepository:
    """Redis-backed job and summary persistence."""

    def __init__(self, client: Redis, keys: RedisKeys, *, ttl_seconds: int) -> None:
        self._client = client
        self._keys = keys
        self._ttl_seconds = ttl_seconds

    def save(self, job: TranscodeJob) -> None:
        existing = self.get(job.id)
        if existing is not None and existing.state != job.state:
            self._client.srem(
                self._keys.job_state_index(existing.state.value),
                str(job.id),
            )

        self._client.set(
            self._keys.job(job.id),
            job.model_dump_json(),
            ex=self._ttl_seconds,
        )
        self._client.sadd(self._keys.job_state_index(job.state.value), str(job.id))

    def get(self, job_id: UUID) -> TranscodeJob | None:
        payload = self._client.get(self._keys.job(job_id))
        if payload is None:
            return None
        return TranscodeJob.model_validate_json(payload)

    def list_by_state(
        self,
        state: JobState,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TranscodeJob]:
        job_ids = self._client.smembers(self._keys.job_state_index(state.value))
        jobs: list[TranscodeJob] = []
        for job_id in job_ids:
            job = self.get(UUID(str(job_id)))
            if job is not None:
                jobs.append(job)

        jobs.sort(key=lambda item: item.created_at, reverse=True)
        return jobs[offset : offset + limit]

    def save_summary(self, summary: JobSummary) -> None:
        self._client.set(
            self._keys.job_summary(summary.job_id),
            summary.model_dump_json(),
            ex=self._ttl_seconds,
        )

    def get_summary(self, job_id: UUID) -> JobSummary | None:
        payload = self._client.get(self._keys.job_summary(job_id))
        if payload is None:
            return None
        return JobSummary.model_validate_json(payload)
