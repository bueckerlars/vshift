from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from vshift.domain.job.job_state import JobState


class HealthResponse(BaseModel):
    """Health check response."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "ok",
                "redis": "ok",
                "version": "0.1.0",
            },
        }
    )

    status: str = Field(description="Overall service status: ok or degraded")
    redis: str = Field(description="Redis connectivity status: ok or error")
    version: str = Field(description="Running vshift version")


class JobResponse(BaseModel):
    """Transcoding job status."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": "00000000-0000-4000-8000-000000000001",
                "input_path": "/data/input/movie.mkv",
                "output_path": "/data/output/movie.mp4",
                "profile_name": "h264_1080p",
                "state": "completed",
                "worker_id": "00000000-0000-4000-8000-000000000002",
                "created_at": "2026-01-01T00:00:00Z",
                "claimed_at": "2026-01-01T00:00:05Z",
                "started_at": "2026-01-01T00:00:06Z",
                "completed_at": "2026-01-01T00:05:00Z",
                "attempt": 1,
                "error_message": None,
                "match_rule_id": "movies_1080p",
            },
        }
    )

    id: UUID
    input_path: Path
    output_path: Path
    profile_name: str
    state: JobState
    worker_id: UUID | None = None
    created_at: datetime
    claimed_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt: int = Field(ge=1)
    error_message: str | None = None
    match_rule_id: str


class JobSummaryResponse(BaseModel):
    """Transcoding statistics for a completed job."""

    job_id: UUID
    input_path: Path
    output_path: Path
    profile_name: str
    input_size_bytes: int = Field(ge=0)
    output_size_bytes: int = Field(ge=0)
    input_duration_seconds: float | None = Field(default=None, ge=0)
    compression_ratio: float | None = None
    wall_clock_seconds: float = Field(ge=0)
    ffmpeg_version: str
    started_at: datetime
    completed_at: datetime
    video_codec_in: str | None = None
    video_codec_out: str
    resolution_in: str | None = None
    resolution_out: str | None = None
