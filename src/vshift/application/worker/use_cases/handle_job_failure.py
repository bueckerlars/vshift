from datetime import UTC, datetime
from uuid import UUID

from loguru import logger

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_state_machine import JobStateMachine
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.exception import VShiftException
from vshift.ports.config_repository import ConfigRepository
from vshift.ports.job_repository import JobRepository
from vshift.ports.task_queue import TaskQueue


class HandleJobFailure:
    """Requeues or fails a job after a transcode error."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        job_repository: JobRepository,
        task_queue: TaskQueue,
        *,
        worker_id: UUID,
    ) -> None:
        self._config_repository = config_repository
        self._job_repository = job_repository
        self._task_queue = task_queue
        self._worker_id = worker_id

    def execute(self, job: TranscodeJob, error: str) -> TranscodeJob:
        if job.worker_id != self._worker_id:
            msg = (
                f"worker {self._worker_id} cannot fail job {job.id} "
                "owned by another worker"
            )
            raise VShiftException(msg)

        if job.state not in {JobState.CLAIMED, JobState.PROCESSING}:
            msg = f"job {job.id} cannot fail from state {job.state}"
            raise VShiftException(msg)

        max_retries = self._config_repository.get_max_retries()
        if job.attempt >= max_retries:
            return self._fail_job(job, error, max_retries)

        return self._requeue_job(job, error, max_retries)

    def _fail_job(
        self,
        job: TranscodeJob,
        error: str,
        max_retries: int,
    ) -> TranscodeJob:
        failed = job.model_copy(
            update={
                "state": JobStateMachine.transition(job.state, JobState.FAILED),
                "worker_id": None,
                "error_message": error,
                "completed_at": datetime.now(tz=UTC),
            },
        )
        self._job_repository.save(failed)
        self._task_queue.push_to_dead_letter(failed.id)
        logger.error(
            "job {} failed permanently after {} attempt(s): {}",
            failed.id,
            failed.attempt,
            error,
        )
        return failed

    def _requeue_job(
        self,
        job: TranscodeJob,
        error: str,
        max_retries: int,
    ) -> TranscodeJob:
        pending = job.model_copy(
            update={
                "state": JobStateMachine.transition(job.state, JobState.PENDING),
                "worker_id": None,
                "claimed_at": None,
                "started_at": None,
                "attempt": job.attempt + 1,
                "error_message": error,
            },
        )
        self._job_repository.save(pending)
        self._task_queue.enqueue(pending.id)
        logger.warning(
            "requeued failed job {} (attempt {}/{}): {}",
            pending.id,
            pending.attempt,
            max_retries,
            error,
        )
        return pending
