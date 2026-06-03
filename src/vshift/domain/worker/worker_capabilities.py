from pydantic import BaseModel, Field


class WorkerCapabilities(BaseModel):
    """Hardware and runtime capabilities reported by a worker at registration."""

    ffmpeg_version: str = Field(
        description="FFmpeg version string from the worker host"
    )
    encoders: list[str] = Field(
        default_factory=list,
        description="Available FFmpeg video encoder names (e.g. libx264, h264_nvenc)",
    )
    max_concurrent_jobs: int = Field(
        default=1,
        ge=1,
        le=1,
        description="Maximum parallel transcode jobs; vshift allows one per worker",
    )
