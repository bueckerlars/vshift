from pathlib import Path

from pydantic import BaseModel, Field


class ProbedInput(BaseModel):
    """Input file metadata used for profile matching."""

    path: Path
    extension: str
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    duration_seconds: float | None = Field(default=None, ge=0)
