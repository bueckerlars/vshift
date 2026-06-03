from dataclasses import dataclass

from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding.transcode_result import TranscodeResult


@dataclass(frozen=True, slots=True)
class TranscodeExecution:
    job: TranscodeJob
    result: TranscodeResult
