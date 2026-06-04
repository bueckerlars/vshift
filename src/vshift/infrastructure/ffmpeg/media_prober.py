from pathlib import Path

from vshift.domain.file.probed_input import ProbedInput
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.ffmpeg.probe import FfmpegProbe


class FfmpegMediaProber:
    """MediaProber adapter backed by ffprobe."""

    def __init__(self, paths: FfmpegPaths | None = None) -> None:
        self._probe = FfmpegProbe(paths)

    def probe(self, path: Path) -> ProbedInput:
        media = self._probe.probe(path)
        extension = path.suffix.lstrip(".").lower()
        return ProbedInput(
            path=path,
            extension=extension,
            width=media.width,
            height=media.height,
            bit_depth=media.bit_depth,
            hdr=media.hdr,
            duration_seconds=media.duration_seconds,
        )
