from datetime import datetime
from pathlib import Path
from uuid import UUID

from pydantic import BaseModel, Field


class JobSummary(BaseModel):
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
