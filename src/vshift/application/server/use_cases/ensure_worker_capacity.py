from loguru import logger

from vshift.application.common.settings import Settings
from vshift.ports.task_queue import TaskQueue
from vshift.ports.worker_pod_launcher import WorkerPodLauncher


class EnsureWorkerCapacity:
    """Launches worker pods when queue depth exceeds active worker capacity."""

    def __init__(
        self,
        settings: Settings,
        task_queue: TaskQueue,
        worker_pod_launcher: WorkerPodLauncher,
    ) -> None:
        self._settings = settings
        self._task_queue = task_queue
        self._worker_pod_launcher = worker_pod_launcher

    def execute(self) -> list[str]:
        if not self._settings.kubernetes.enabled:
            return []

        queue_depth = self._task_queue.depth()
        if queue_depth <= 0:
            return []

        active_workers = self._worker_pod_launcher.count_active_workers()
        max_pods = self._settings.kubernetes.max_concurrent_pods
        desired_workers = min(queue_depth, max_pods)
        to_launch = max(0, desired_workers - active_workers)

        launched: list[str] = []
        for _ in range(to_launch):
            launched.append(self._worker_pod_launcher.launch_worker())

        if launched:
            logger.info(
                "launched {} kubernetes worker pod(s); queue={}, active={}, max={}",
                len(launched),
                queue_depth,
                active_workers,
                max_pods,
            )
        return launched
