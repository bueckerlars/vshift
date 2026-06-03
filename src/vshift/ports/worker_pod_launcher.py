from typing import Protocol


class WorkerPodLauncher(Protocol):
    """Launches ephemeral worker pods (e.g. Kubernetes Jobs)."""

    def count_active_workers(self) -> int: ...

    def launch_worker(self) -> str: ...
