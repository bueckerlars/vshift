from pathlib import Path

from pydantic import BaseModel, Field


class TranscodeResult(BaseModel):
    output_path: Path
    wall_clock_seconds: float = Field(ge=0)
    ffmpeg_version: str
    video_codec_out: str
    resolution_out: str | None = None
