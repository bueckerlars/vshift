from pathlib import Path
from typing import Protocol
from uuid import UUID


class ProcessedFileStore(Protocol):
    """Tracks input files that have already been enqueued for transcoding."""

    def is_processed(self, input_path: Path) -> bool: ...

    def mark_processed(self, input_path: Path, job_id: UUID) -> None: ...
