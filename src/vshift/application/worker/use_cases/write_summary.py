from datetime import UTC, datetime

from loguru import logger

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_state_machine import JobStateMachine
from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding.transcode_result import TranscodeResult
from vshift.exception import VShiftException
from vshift.ports.job_repository import JobRepository
from vshift.ports.transcoder import Transcoder


class WriteSummary:
    """Persists the job summary and marks the job as completed."""

    def __init__(
        self,
        job_repository: JobRepository,
        transcoder: Transcoder,
    ) -> None:
        self._job_repository = job_repository
        self._transcoder = transcoder

    def execute(self, job: TranscodeJob, result: TranscodeResult) -> JobSummary:
        if job.state != JobState.PROCESSING:
            msg = (
                f"job {job.id} must be processing to write summary (state={job.state})"
            )
            raise VShiftException(msg)

        summary = self._transcoder.build_summary(job, result)
        self._job_repository.save_summary(summary)

        completed = job.model_copy(
            update={
                "state": JobStateMachine.transition(job.state, JobState.COMPLETED),
                "completed_at": datetime.now(tz=UTC),
                "error_message": None,
            },
        )
        self._job_repository.save(completed)
        logger.info("job {} completed successfully", completed.id)
        return summary
