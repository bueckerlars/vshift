from typing import Protocol

from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding.transcode_result import TranscodeResult


class Transcoder(Protocol):
    """Executes FFmpeg transcoding for a job."""

    def transcode(self, job: TranscodeJob) -> TranscodeResult: ...

    def build_summary(
        self,
        job: TranscodeJob,
        result: TranscodeResult,
    ) -> JobSummary: ...
