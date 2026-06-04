from pathlib import Path

from pydantic import BaseModel, Field


class ProbedInput(BaseModel):
    """Input file metadata used for profile matching."""

    path: Path
    extension: str
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    bit_depth: int | None = Field(
        default=None,
        description="Detected video bit depth (8, 10, or 12)",
    )
    hdr: bool | None = Field(
        default=None,
        description="Whether the source video carries HDR signaling",
    )
    duration_seconds: float | None = Field(default=None, ge=0)
