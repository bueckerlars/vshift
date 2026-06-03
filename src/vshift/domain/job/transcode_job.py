from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field

from vshift.domain.job.job_state import JobState
from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile


class TranscodeJob(BaseModel):
    id: UUID
    input_path: Path
    output_path: Path
    profile_name: str
    profile_snapshot: VshiftProfile
    state: JobState
    worker_id: UUID | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt: int = Field(default=1, ge=1)
    error_message: str | None = None
    match_rule_id: str
