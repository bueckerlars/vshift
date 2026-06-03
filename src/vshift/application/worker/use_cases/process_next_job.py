from loguru import logger

from vshift.application.worker.use_cases.claim_job import ClaimJob
from vshift.application.worker.use_cases.execute_transcode import ExecuteTranscode
from vshift.application.worker.use_cases.handle_job_failure import HandleJobFailure
from vshift.application.worker.use_cases.write_summary import WriteSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.exception import VShiftException
from vshift.ports.job_repository import JobRepository


class ProcessNextJob:
    """Claims and processes a single job from the queue."""

    def __init__(
        self,
        claim_job: ClaimJob,
        execute_transcode: ExecuteTranscode,
        write_summary: WriteSummary,
        handle_job_failure: HandleJobFailure,
        job_repository: JobRepository,
    ) -> None:
        self._claim_job = claim_job
        self._execute_transcode = execute_transcode
        self._write_summary = write_summary
        self._handle_job_failure = handle_job_failure
        self._job_repository = job_repository

    def execute(self) -> TranscodeJob | None:
        job = self._claim_job.execute()
        if job is None:
            return None

        try:
            execution = self._execute_transcode.execute(job)
            self._write_summary.execute(execution.job, execution.result)
        except VShiftException as error:
            current = self._job_repository.get(job.id) or job
            logger.exception("job {} failed", current.id)
            return self._handle_job_failure.execute(current, str(error))

        completed = self._job_repository.get(job.id)
        return completed or job
