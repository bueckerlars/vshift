# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportAttributeAccessIssue=false, reportOptionalMemberAccess=false, reportGeneralTypeIssues=false

from kubernetes import client
from kubernetes.client.rest import ApiException
from loguru import logger

from vshift.application.common.settings import Settings
from vshift.exception import VShiftException
from vshift.infrastructure.kubernetes.client import create_batch_api
from vshift.infrastructure.kubernetes.worker_pod_factory import (
    WORKER_APP_LABEL,
    WORKER_COMPONENT_LABEL,
    WORKER_MANAGED_BY_LABEL,
    K8sWorkerPodFactory,
)


class K8sWorkerPodLauncher:
    """Creates Kubernetes Jobs for one-shot worker pods."""

    def __init__(
        self,
        settings: Settings,
        *,
        batch_api: client.BatchV1Api | None = None,
        factory: K8sWorkerPodFactory | None = None,
    ) -> None:
        self._settings = settings
        self._k8s = settings.kubernetes
        self._batch_api = batch_api or create_batch_api(self._k8s)
        self._factory = factory or K8sWorkerPodFactory(settings)

    def count_active_workers(self) -> int:
        label_selector = (
            f"app.kubernetes.io/name={WORKER_APP_LABEL},"
            f"app.kubernetes.io/component={WORKER_COMPONENT_LABEL},"
            f"app.kubernetes.io/managed-by={WORKER_MANAGED_BY_LABEL}"
        )
        try:
            jobs = self._batch_api.list_namespaced_job(
                namespace=self._k8s.namespace,
                label_selector=label_selector,
            )
        except ApiException as error:
            msg = f"failed to list worker jobs: {error.reason}"
            raise VShiftException(msg) from error

        active = 0
        for job in jobs.items:
            if _is_active_job(job):
                active += 1
        return active

    def launch_worker(self) -> str:
        job_name = self._factory.build_job_name()
        job = self._factory.build_job(job_name=job_name)
        try:
            self._batch_api.create_namespaced_job(
                namespace=self._k8s.namespace,
                body=job,
            )
        except ApiException as error:
            msg = f"failed to create worker job {job_name}: {error.reason}"
            raise VShiftException(msg) from error

        logger.info("launched kubernetes worker job {}", job_name)
        return job_name


def _is_active_job(job: client.V1Job) -> bool:
    status = job.status
    if status is None:
        return True
    if status.active and status.active > 0:
        return True
    if status.succeeded is not None and status.succeeded > 0:
        return False
    if status.failed is not None and status.failed > 0:
        return False
    return status.completion_time is None
