from datetime import UTC, datetime

from loguru import logger

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_state_machine import JobStateMachine
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.ports.config_repository import ConfigRepository
from vshift.ports.job_repository import JobRepository
from vshift.ports.task_queue import TaskQueue
from vshift.ports.worker_registry import WorkerRegistry


class RecoverStaleJobs:
    """Requeues or fails jobs whose worker heartbeat has expired."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        job_repository: JobRepository,
        task_queue: TaskQueue,
        worker_registry: WorkerRegistry,
    ) -> None:
        self._config_repository = config_repository
        self._job_repository = job_repository
        self._task_queue = task_queue
        self._worker_registry = worker_registry

    def execute(self) -> list[TranscodeJob]:
        max_retries = self._config_repository.get_max_retries()
        recovered: list[TranscodeJob] = []

        for state in (JobState.CLAIMED, JobState.PROCESSING):
            for job in self._job_repository.list_by_state(state):
                if self._worker_registry.is_job_alive(job.id):
                    continue

                updated = self._recover_job(job, max_retries)
                recovered.append(updated)

        if recovered:
            logger.info("recovered {} stale job(s)", len(recovered))
        return recovered

    def _recover_job(self, job: TranscodeJob, max_retries: int) -> TranscodeJob:
        if job.attempt >= max_retries:
            failed = job.model_copy(
                update={
                    "state": JobStateMachine.transition(job.state, JobState.FAILED),
                    "worker_id": None,
                    "error_message": "worker heartbeat expired",
                    "completed_at": datetime.now(tz=UTC),
                },
            )
            self._job_repository.save(failed)
            self._task_queue.push_to_dead_letter(failed.id)
            logger.warning(
                "job {} moved to dead letter queue after {} attempt(s)",
                failed.id,
                failed.attempt,
            )
            return failed

        pending = job.model_copy(
            update={
                "state": JobStateMachine.transition(job.state, JobState.PENDING),
                "worker_id": None,
                "claimed_at": None,
                "started_at": None,
                "attempt": job.attempt + 1,
                "error_message": "worker heartbeat expired; requeued",
            },
        )
        self._job_repository.save(pending)
        self._task_queue.enqueue(pending.id)
        logger.warning(
            "requeued stale job {} (attempt {}/{})",
            pending.id,
            pending.attempt,
            max_retries,
        )
        return pending
