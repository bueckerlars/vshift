from typing import Protocol
from uuid import UUID

from vshift.domain.worker.worker_info import WorkerInfo


class WorkerRegistry(Protocol):
    """Tracks active worker processes."""

    def register(self, worker: WorkerInfo) -> None: ...

    def heartbeat(self, worker_id: UUID) -> None: ...

    def deregister(self, worker_id: UUID) -> None: ...

    def list_workers(self) -> list[WorkerInfo]: ...

    def set_job_heartbeat(self, job_id: UUID, worker_id: UUID) -> None: ...

    def is_job_alive(self, job_id: UUID) -> bool: ...
