# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false

from uuid import UUID

import pytest

from vshift.application.common.settings import Settings
from vshift.application.server.use_cases.ensure_worker_capacity import (
    EnsureWorkerCapacity,
)
from vshift.infrastructure.kubernetes.worker_pod_factory import K8sWorkerPodFactory


@pytest.fixture
def settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    monkeypatch.setenv("VSHIFT__REDIS__PASSWORD", "secret")
    base = Settings()
    return base.model_copy(
        update={
            "kubernetes": base.kubernetes.model_copy(
                update={
                    "enabled": True,
                    "worker_image": "vshift:test",
                    "config_map_name": "vshift-config",
                    "input_volume_claim": "vshift-input",
                    "output_volume_claim": "vshift-output",
                    "temp_volume_claim": "vshift-temp",
                },
            ),
        },
    )


def test_worker_pod_factory_builds_one_shot_job(settings: Settings) -> None:
    factory = K8sWorkerPodFactory(settings)
    job = factory.build_job(job_name="vshift-worker-deadbeef")

    assert job.metadata is not None
    assert job.metadata.name == "vshift-worker-deadbeef"
    assert job.spec is not None
    assert job.spec.backoff_limit == 0
    assert (
        job.spec.ttl_seconds_after_finished
        == settings.kubernetes.job_ttl_seconds_after_finished
    )

    template = job.spec.template
    assert template is not None
    pod_spec = template.spec
    assert pod_spec is not None
    assert pod_spec.restart_policy == "Never"
    assert pod_spec.service_account_name == "vshift-worker"

    container = pod_spec.containers[0]
    assert container.image == "vshift:test"
    assert container.command == ["vshift-worker"]
    env = {item.name: item.value for item in container.env or []}
    assert env["VSHIFT__WORKER__ONE_SHOT"] == "true"
    assert env["VSHIFT__REDIS__HOST"] == settings.redis.host
    assert env["VSHIFT__FFMPEG__THREAD_COUNT"] == "2"

    assert container.resources is not None
    assert container.resources.requests is not None
    assert container.resources.limits is not None
    assert container.resources.requests["cpu"] == "1500m"
    assert container.resources.requests["memory"] == "3Gi"
    assert container.resources.limits["cpu"] == "3"
    assert container.resources.limits["memory"] == "5Gi"

    volume_names = {mount.name for mount in container.volume_mounts or []}
    assert volume_names == {"config", "input", "output", "temp"}


def test_worker_pod_factory_labels(settings: Settings) -> None:
    factory = K8sWorkerPodFactory(settings)
    job = factory.build_job(job_name="vshift-worker-abc12345")

    assert job.metadata is not None
    assert job.metadata.labels is not None
    assert job.metadata.labels["app.kubernetes.io/name"] == "vshift"
    assert job.metadata.labels["app.kubernetes.io/component"] == "worker"


class StubWorkerPodLauncher:
    def __init__(self, *, active: int = 0) -> None:
        self.active = active
        self.launched: list[str] = []

    def count_active_workers(self) -> int:
        return self.active

    def launch_worker(self) -> str:
        name = f"vshift-worker-{len(self.launched)}"
        self.launched.append(name)
        self.active += 1
        return name


class StubTaskQueue:
    def __init__(self, depth: int) -> None:
        self._depth = depth

    def enqueue(self, job_id: UUID) -> None:
        del job_id

    def dequeue(self, *, timeout_seconds: int = 0) -> UUID | None:
        del timeout_seconds
        return None

    def requeue(self, job_id: UUID) -> None:
        del job_id

    def push_to_dead_letter(self, job_id: UUID) -> None:
        del job_id

    def depth(self) -> int:
        return self._depth


def test_ensure_worker_capacity_launches_pods(settings: Settings) -> None:
    settings = settings.model_copy(
        update={
            "kubernetes": settings.kubernetes.model_copy(
                update={"max_concurrent_pods": 5},
            ),
        },
    )
    launcher = StubWorkerPodLauncher(active=1)
    use_case = EnsureWorkerCapacity(
        settings,
        StubTaskQueue(depth=4),
        launcher,
    )

    launched = use_case.execute()

    assert launched == [
        "vshift-worker-0",
        "vshift-worker-1",
        "vshift-worker-2",
    ]
    assert launcher.active == 4


def test_ensure_worker_capacity_respects_max_pods(settings: Settings) -> None:
    settings = settings.model_copy(
        update={
            "kubernetes": settings.kubernetes.model_copy(
                update={"max_concurrent_pods": 2},
            ),
        },
    )
    launcher = StubWorkerPodLauncher(active=0)
    use_case = EnsureWorkerCapacity(
        settings,
        StubTaskQueue(depth=10),
        launcher,
    )

    launched = use_case.execute()

    assert len(launched) == 2


def test_ensure_worker_capacity_skips_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VSHIFT__REDIS__PASSWORD", "secret")
    settings = Settings()
    launcher = StubWorkerPodLauncher()
    use_case = EnsureWorkerCapacity(
        settings,
        StubTaskQueue(depth=5),
        launcher,
    )

    assert use_case.execute() == []
