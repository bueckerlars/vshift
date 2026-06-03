from datetime import UTC, datetime
from uuid import UUID

from loguru import logger

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_state_machine import JobStateMachine
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.ports.job_repository import JobRepository
from vshift.ports.task_queue import TaskQueue
from vshift.ports.worker_registry import WorkerRegistry


class ClaimJob:
    """Claims the next pending job from the queue."""

    def __init__(
        self,
        job_repository: JobRepository,
        task_queue: TaskQueue,
        worker_registry: WorkerRegistry,
        *,
        worker_id: UUID,
        dequeue_timeout_seconds: int = 5,
    ) -> None:
        self._job_repository = job_repository
        self._task_queue = task_queue
        self._worker_registry = worker_registry
        self._worker_id = worker_id
        self._dequeue_timeout_seconds = dequeue_timeout_seconds

    def execute(self) -> TranscodeJob | None:
        job_id = self._task_queue.dequeue(
            timeout_seconds=self._dequeue_timeout_seconds,
        )
        if job_id is None:
            return None

        job = self._job_repository.get(job_id)
        if job is None:
            logger.warning("queue contained unknown job id {}", job_id)
            return None

        if job.state != JobState.PENDING:
            logger.warning(
                "skipping job {} in unexpected state {}",
                job_id,
                job.state,
            )
            return None

        claimed = job.model_copy(
            update={
                "state": JobStateMachine.transition(job.state, JobState.CLAIMED),
                "worker_id": self._worker_id,
                "claimed_at": datetime.now(tz=UTC),
            },
        )
        self._job_repository.save(claimed)
        self._worker_registry.set_job_heartbeat(claimed.id, self._worker_id)
        self._worker_registry.heartbeat(self._worker_id)
        logger.info("worker {} claimed job {}", self._worker_id, claimed.id)
        return claimed
