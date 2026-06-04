from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, Field, PositiveInt, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from vshift.exception import VShiftException


class LoggingSettings(BaseModel):
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "TRACE"] = Field(
        default="INFO", description="Logging level"
    )


class ApplicationSettings(BaseModel):
    worker_threads: PositiveInt = Field(
        default=1, description="Number of worker threads"
    )


class DirectorySettings(BaseModel):
    """
    Settings for input, output, and temporary directories.
    """

    input_dir: str = Field(
        default="data/input", description="Directory for input files"
    )

    output_dir: str = Field(
        default="data/output", description="Directory for output files"
    )

    temp_dir: str = Field(
        default="data/temp", description="Directory for temporary files"
    )

    profile_dir: str = Field(
        default="data/profile", description="Directory for profile files"
    )


class RedisConnectionSettings(BaseModel):
    """
    Settings for the Redis connection.
    """

    host: str = Field(default="localhost", description="Redis host")

    port: PositiveInt = Field(default=6379, description="Redis port")

    password: SecretStr = Field(default=..., description="Redis password")

    database: PositiveInt = Field(default=0, description="Redis database")

    @model_validator(mode="after")
    def validate_password(self) -> Self:
        if not self.password.get_secret_value():
            raise VShiftException("Redis password is required")
        return self


class FfmpegSettings(BaseModel):
    ffmpeg_path: str = Field(default="ffmpeg", description="Path to ffmpeg binary")
    ffprobe_path: str = Field(default="ffprobe", description="Path to ffprobe binary")
    thread_count: PositiveInt | None = Field(
        default=2,
        description="FFmpeg -threads cap; reduces CPU oversubscription on workers",
    )


class ConfigSettings(BaseModel):
    file: Path = Field(
        default=Path("config/vshift.yaml"),
        description="Path to the vshift YAML configuration file",
    )


class QueueSettings(BaseModel):
    """Settings for Redis-backed queues and job storage."""

    key_prefix: str = Field(default="vshift", min_length=1)
    ttl: PositiveInt = Field(
        default=60 * 60 * 24,
        description="Time to live for persisted jobs and summaries in seconds",
    )
    job_heartbeat_ttl_seconds: PositiveInt = Field(default=60)
    worker_ttl_seconds: PositiveInt = Field(default=30)


class ApiSettings(BaseModel):
    """Settings for the REST API server."""

    host: str = Field(default="0.0.0.0")
    port: PositiveInt = Field(default=8000)
    docs_enabled: bool = Field(
        default=True,
        description="Expose Swagger UI, ReDoc, and the OpenAPI schema",
    )
    docs_url: str = Field(default="/docs", description="Swagger UI path")
    redoc_url: str = Field(default="/redoc", description="ReDoc UI path")
    openapi_url: str = Field(default="/openapi.json", description="OpenAPI schema path")


class ServerRuntimeSettings(BaseModel):
    """Background task intervals for the server process."""

    scan_interval_seconds: PositiveInt = Field(default=30)
    recovery_interval_seconds: PositiveInt = Field(default=60)
    worker_scale_interval_seconds: PositiveInt = Field(default=15)


class K8sResourceSpec(BaseModel):
    cpu: str | None = Field(default=None)
    memory: str | None = Field(default=None)

    def to_dict(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self.cpu is not None:
            values["cpu"] = self.cpu
        if self.memory is not None:
            values["memory"] = self.memory
        return values


class K8sContainerResources(BaseModel):
    requests: K8sResourceSpec = Field(default_factory=K8sResourceSpec)
    limits: K8sResourceSpec = Field(default_factory=K8sResourceSpec)


def _default_worker_resources() -> K8sContainerResources:
    # Sized for ~8 GiB RAM / 4 CPU nodes (one 4K transcode per node).
    return K8sContainerResources(
        requests=K8sResourceSpec(cpu="1500m", memory="3Gi"),
        limits=K8sResourceSpec(cpu="3", memory="5Gi"),
    )


class KubernetesSettings(BaseModel):
    """Kubernetes integration for dynamic worker Job pods."""

    enabled: bool = Field(default=False)
    namespace: str = Field(default="default", min_length=1)
    in_cluster: bool = Field(default=True)
    worker_image: str = Field(default="ghcr.io/bueckerlars/vshift:latest", min_length=1)
    worker_image_pull_policy: str = Field(default="IfNotPresent")
    max_concurrent_pods: PositiveInt = Field(
        default=1,
        description=(
            "Max simultaneous worker Job pods; use node count on multi-node clusters"
        ),
    )
    worker_resources: K8sContainerResources = Field(
        default_factory=_default_worker_resources,
        description="CPU/memory requests and limits for dynamic worker Job pods",
    )
    worker_service_account: str = Field(default="vshift-worker", min_length=1)
    job_ttl_seconds_after_finished: PositiveInt = Field(default=3600)
    input_volume_claim: str | None = Field(default=None)
    output_volume_claim: str | None = Field(default=None)
    temp_volume_claim: str | None = Field(default=None)
    input_mount_path: str = Field(default="/data/input")
    output_mount_path: str = Field(default="/data/output")
    temp_mount_path: str = Field(default="/data/temp")
    config_mount_path: str = Field(default="/app/config")
    config_map_name: str | None = Field(default="vshift-config")


class WorkerRuntimeSettings(BaseModel):
    """Runtime settings for the worker process."""

    idle_sleep_seconds: PositiveInt = Field(default=1)
    claim_dequeue_timeout_seconds: PositiveInt = Field(default=5)
    one_shot: bool = Field(
        default=False,
        description="Process a single job and exit (for Kubernetes Job pods)",
    )


class Settings(BaseSettings):
    """
    Application settings.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        env_prefix="VSHIFT__",
        case_sensitive=False,
        extra="ignore",
    )

    application: ApplicationSettings = Field(default_factory=ApplicationSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    directories: DirectorySettings = Field(default_factory=DirectorySettings)
    config: ConfigSettings = Field(default_factory=ConfigSettings)
    ffmpeg: FfmpegSettings = Field(default_factory=FfmpegSettings)
    redis: RedisConnectionSettings = Field(default_factory=RedisConnectionSettings)  # type: ignore
    queue: QueueSettings = Field(default_factory=QueueSettings)
    api: ApiSettings = Field(default_factory=ApiSettings)
    server: ServerRuntimeSettings = Field(default_factory=ServerRuntimeSettings)
    worker: WorkerRuntimeSettings = Field(default_factory=WorkerRuntimeSettings)
    kubernetes: KubernetesSettings = Field(default_factory=KubernetesSettings)
