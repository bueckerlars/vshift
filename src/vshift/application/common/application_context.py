import sys
from functools import cached_property

from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from vshift import __app_name__, __version__
from vshift.application.common.settings import Settings
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.ffmpeg.transcoder import FfmpegTranscoder
from vshift.infrastructure.filesystem.yaml_config_repository import YamlConfigRepository
from vshift.infrastructure.redis.factory import RedisStores, create_redis_stores


class ApplicationContext:
    """
    Application context is used for dependency injection and configuration.
    """

    def __init__(self) -> None:
        self._init_logger()

    def _init_logger(self) -> None:

        logger.add(sys.stderr, level="INFO")

    @cached_property
    def settings(self) -> Settings:
        return Settings()

    @cached_property
    def config_repository(self) -> YamlConfigRepository:
        return YamlConfigRepository(self.settings.config.file)

    @cached_property
    def redis_stores(self) -> RedisStores:
        return create_redis_stores(self.settings.redis, self.settings.queue)

    @cached_property
    def transcoder(self) -> FfmpegTranscoder:
        paths = FfmpegPaths(
            ffmpeg=self.settings.ffmpeg.ffmpeg_path,
            ffprobe=self.settings.ffmpeg.ffprobe_path,
        )
        return FfmpegTranscoder(
            paths=paths,
            thread_count=self.settings.ffmpeg.thread_count,
        )

    def log_settings(self) -> None:
        table = Table(show_header=True, header_style="bold")
        table.add_column("Setting", style="cyan", no_wrap=True)
        table.add_column("Value", style="green")

        table.add_row("Name", __app_name__)
        table.add_row("Version", __version__)

        for section_name, rows in _settings_sections(self.settings):
            table.add_section()
            table.add_row(section_name, "", style="bold")
            for property_name, value in rows:
                table.add_row(property_name, value)

        Console(stderr=True).print(table)


def _settings_sections(model: BaseModel) -> list[tuple[str, list[tuple[str, str]]]]:
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    model_type = type(model)
    for name in model_type.model_fields:
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            value_type = type(value)
            rows = [
                (field_name, str(getattr(value, field_name)))
                for field_name in value_type.model_fields
            ]
            sections.append((name, rows))
    return sections
