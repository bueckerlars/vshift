from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from vshift.domain.file.probed_input import ProbedInput


class FileScanner(Protocol):
    """Watches the input directory for stable, ready-to-process files."""

    def start(self, handler: Callable[[ProbedInput], None]) -> None: ...

    def stop(self) -> None: ...

    def scan_once(self, input_dir: Path) -> list[ProbedInput]: ...
