from typing import Protocol
from uuid import UUID

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob


class JobRepository(Protocol):
    """Persists and retrieves transcoding jobs."""

    def save(self, job: TranscodeJob) -> None: ...

    def get(self, job_id: UUID) -> TranscodeJob | None: ...

    def list_by_state(
        self,
        state: JobState,
        *,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TranscodeJob]: ...

    def save_summary(self, summary: JobSummary) -> None: ...

    def get_summary(self, job_id: UUID) -> JobSummary | None: ...
