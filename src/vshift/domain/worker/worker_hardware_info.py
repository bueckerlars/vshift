from pydantic import BaseModel, Field


class WorkerHardwareInfo(BaseModel):
    """Static hardware description of the worker host."""

    platform: str = Field(
        description="Operating system family (e.g. linux, darwin, windows)"
    )
    architecture: str = Field(description="CPU architecture (e.g. x86_64, aarch64)")
    cpu_model: str | None = Field(
        default=None,
        description="CPU model name when available",
    )
    cpu_cores: int | None = Field(
        default=None,
        ge=1,
        description="Logical CPU core count",
    )
    memory_total_bytes: int | None = Field(
        default=None,
        ge=1,
        description="Total system memory in bytes",
    )
    gpu_devices: list[str] = Field(
        default_factory=list,
        description="Detected GPU device names (e.g. for NVENC, QSV, VAAPI)",
    )
