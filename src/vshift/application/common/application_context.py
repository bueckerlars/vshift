import sys
from functools import cached_property

from loguru import logger
from pydantic import BaseModel
from rich.console import Console
from rich.table import Table

from vshift import __app_name__, __version__
from vshift.application.common.settings import Settings


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

    def _log_settings(self) -> None:
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
    for name in model.model_fields:
        value = getattr(model, name)
        if isinstance(value, BaseModel):
            rows = [
                (field_name, str(getattr(value, field_name)))
                for field_name in value.model_fields
            ]
            sections.append((name, rows))
    return sections
