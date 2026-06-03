from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

from vshift.domain.file.probed_input import ProbedInput


class PollFileScanner:
    """Polls an input directory for files stable enough to transcode."""

    def __init__(self, *, file_stability_seconds: int) -> None:
        self._file_stability_seconds = file_stability_seconds
        self._handler: Callable[[ProbedInput], None] | None = None
        self._running = False

    def start(self, handler: Callable[[ProbedInput], None]) -> None:
        self._handler = handler
        self._running = True

    def stop(self) -> None:
        self._running = False
        self._handler = None

    def scan_once(self, input_dir: Path) -> list[ProbedInput]:
        if not input_dir.is_dir():
            return []

        now = time.time()
        discovered: list[ProbedInput] = []
        for path in sorted(input_dir.rglob("*")):
            if not path.is_file() or _is_hidden(path):
                continue
            if not _is_stable(path, now, self._file_stability_seconds):
                continue

            probed = ProbedInput(
                path=path,
                extension=path.suffix.lstrip(".").lower(),
            )
            discovered.append(probed)
            if self._running and self._handler is not None:
                self._handler(probed)

        return discovered


def _is_hidden(path: Path) -> bool:
    return any(part.startswith(".") for part in path.parts)


def _is_stable(path: Path, now: float, stability_seconds: int) -> bool:
    stat = path.stat()
    if stat.st_size <= 0:
        return False
    return (now - stat.st_mtime) >= stability_seconds
