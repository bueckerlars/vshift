"""Import shim for the python-ffmpeg package (docstrings trigger SyntaxWarning)."""

from __future__ import annotations

import warnings

warnings.filterwarnings("ignore", category=SyntaxWarning, module=r"ffmpeg(\.|$)")

import ffmpeg as ffmpeg  # noqa: E402
from ffmpeg.exceptions import FFMpegExecuteError  # noqa: E402

__all__ = ["ffmpeg", "FFMpegExecuteError"]
