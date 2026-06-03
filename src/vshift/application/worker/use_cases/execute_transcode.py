from datetime import UTC, datetime
from uuid import UUID

from loguru import logger

from vshift.application.worker.use_cases.models import TranscodeExecution
from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_state_machine import JobStateMachine
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.exception import VShiftException
from vshift.ports.job_repository import JobRepository
from vshift.ports.transcoder import Transcoder
from vshift.ports.worker_registry import WorkerRegistry


class ExecuteTranscode:
    """Runs FFmpeg for a claimed job."""

    def __init__(
        self,
        job_repository: JobRepository,
        worker_registry: WorkerRegistry,
        transcoder: Transcoder,
        *,
        worker_id: UUID,
    ) -> None:
        self._job_repository = job_repository
        self._worker_registry = worker_registry
        self._transcoder = transcoder
        self._worker_id = worker_id

    def execute(self, job: TranscodeJob) -> TranscodeExecution:
        self._assert_worker_owns_job(job)

        processing = job.model_copy(
            update={
                "state": JobStateMachine.transition(job.state, JobState.PROCESSING),
                "started_at": datetime.now(tz=UTC),
            },
        )
        self._job_repository.save(processing)
        self._worker_registry.set_job_heartbeat(processing.id, self._worker_id)

        logger.info("worker {} transcoding job {}", self._worker_id, processing.id)
        result = self._transcoder.transcode(processing)
        return TranscodeExecution(job=processing, result=result)

    def _assert_worker_owns_job(self, job: TranscodeJob) -> None:
        if job.worker_id != self._worker_id:
            msg = (
                f"worker {self._worker_id} cannot transcode job {job.id} "
                f"owned by {job.worker_id}"
            )
            raise VShiftException(msg)
        if job.state not in {JobState.CLAIMED, JobState.PROCESSING}:
            msg = f"job {job.id} is not ready for transcoding (state={job.state})"
            raise VShiftException(msg)
