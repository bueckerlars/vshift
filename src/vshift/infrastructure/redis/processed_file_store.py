from pathlib import Path
from uuid import UUID

from redis import Redis

from vshift.infrastructure.redis.keys import RedisKeys


class RedisProcessedFileStore:
    """Tracks input files that have already been enqueued."""

    def __init__(self, client: Redis, keys: RedisKeys) -> None:
        self._client = client
        self._keys = keys

    def is_processed(self, input_path: Path) -> bool:
        key = self._keys.processed_file(_canonical_path(input_path))
        return self._client.exists(key) > 0

    def mark_processed(self, input_path: Path, job_id: UUID) -> None:
        self._client.set(
            self._keys.processed_file(_canonical_path(input_path)),
            str(job_id),
        )


def _canonical_path(path: Path) -> str:
    return str(path.expanduser().resolve())
