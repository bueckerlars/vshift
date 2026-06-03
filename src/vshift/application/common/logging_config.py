import sys

from loguru import logger

from vshift.application.common.settings import Settings


def configure_logging(settings: Settings) -> None:
    logger.remove()
    logger.add(sys.stderr, level=settings.logging.level)
