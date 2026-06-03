from pathlib import Path
from typing import Protocol

from vshift.domain.file.probed_input import ProbedInput


class MediaProber(Protocol):
    """Reads video metadata from media files."""

    def probe(self, path: Path) -> ProbedInput: ...
