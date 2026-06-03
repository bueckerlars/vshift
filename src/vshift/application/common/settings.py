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


class QueueSettings(BaseModel):
    """
    Settings for the queue.
    """

    ttl: PositiveInt = Field(
        default=60 * 60 * 24,  # 24 hours
        description="Time to live for the queues",
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
    redis: RedisConnectionSettings = Field(default_factory=RedisConnectionSettings)  # type: ignore
    queue: QueueSettings = Field(default_factory=QueueSettings)
