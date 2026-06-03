from uuid import uuid4

from kubernetes import client  # pyright: ignore[reportMissingTypeStubs]

from vshift.application.common.settings import Settings

WORKER_APP_LABEL = "vshift"
WORKER_COMPONENT_LABEL = "worker"
WORKER_MANAGED_BY_LABEL = "vshift-server"


class K8sWorkerPodFactory:
    """Builds Kubernetes Job specs for one-shot vshift workers."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._k8s = settings.kubernetes

    def build_job_name(self) -> str:
        return f"vshift-worker-{uuid4().hex[:8]}"

    def build_job(self, *, job_name: str) -> client.V1Job:
        k8s = self._k8s
        labels = {
            "app.kubernetes.io/name": WORKER_APP_LABEL,
            "app.kubernetes.io/component": WORKER_COMPONENT_LABEL,
            "app.kubernetes.io/managed-by": WORKER_MANAGED_BY_LABEL,
        }

        container = client.V1Container(
            name="worker",
            image=k8s.worker_image,
            image_pull_policy=k8s.worker_image_pull_policy,
            command=["vshift-worker"],
            env=self._worker_env(),
            volume_mounts=self._volume_mounts(),
        )

        pod_spec = client.V1PodSpec(
            restart_policy="Never",
            service_account_name=k8s.worker_service_account,
            containers=[container],
            volumes=self._volumes(),
        )

        job_spec = client.V1JobSpec(
            ttl_seconds_after_finished=k8s.job_ttl_seconds_after_finished,
            backoff_limit=0,
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels=labels),
                spec=pod_spec,
            ),
        )

        return client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name=job_name, labels=labels),
            spec=job_spec,
        )

    def _worker_env(self) -> list[client.V1EnvVar]:
        app = self._settings
        env_values = {
            "VSHIFT__REDIS__HOST": app.redis.host,
            "VSHIFT__REDIS__PASSWORD": app.redis.password.get_secret_value(),
            "VSHIFT__REDIS__DATABASE": str(app.redis.database),
            "VSHIFT__REDIS__PORT": str(app.redis.port),
            "VSHIFT__CONFIG__FILE": f"{self._k8s.config_mount_path}/vshift.yaml",
            "VSHIFT__WORKER__ONE_SHOT": "true",
            "VSHIFT__LOGGING__LEVEL": app.logging.level,
        }
        return [
            client.V1EnvVar(name=name, value=value)
            for name, value in env_values.items()
        ]

    def _volume_mounts(self) -> list[client.V1VolumeMount]:
        k8s = self._k8s
        mounts: list[client.V1VolumeMount] = []
        if k8s.config_map_name is not None:
            mounts.append(
                client.V1VolumeMount(
                    name="config",
                    mount_path=k8s.config_mount_path,
                    read_only=True,
                ),
            )
        if k8s.input_volume_claim is not None:
            mounts.append(
                client.V1VolumeMount(name="input", mount_path=k8s.input_mount_path),
            )
        if k8s.output_volume_claim is not None:
            mounts.append(
                client.V1VolumeMount(name="output", mount_path=k8s.output_mount_path),
            )
        if k8s.temp_volume_claim is not None:
            mounts.append(
                client.V1VolumeMount(name="temp", mount_path=k8s.temp_mount_path),
            )
        return mounts

    def _volumes(self) -> list[client.V1Volume]:
        k8s = self._k8s
        volumes: list[client.V1Volume] = []
        if k8s.config_map_name is not None:
            volumes.append(
                client.V1Volume(
                    name="config",
                    config_map=client.V1ConfigMapVolumeSource(
                        name=k8s.config_map_name,
                    ),
                ),
            )
        if k8s.input_volume_claim is not None:
            volumes.append(self._pvc_volume("input", k8s.input_volume_claim))
        if k8s.output_volume_claim is not None:
            volumes.append(self._pvc_volume("output", k8s.output_volume_claim))
        if k8s.temp_volume_claim is not None:
            volumes.append(self._pvc_volume("temp", k8s.temp_volume_claim))
        return volumes

    @staticmethod
    def _pvc_volume(name: str, claim_name: str) -> client.V1Volume:
        return client.V1Volume(
            name=name,
            persistent_volume_claim=client.V1PersistentVolumeClaimVolumeSource(
                claim_name=claim_name,
            ),
        )
