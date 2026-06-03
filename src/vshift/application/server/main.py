import uvicorn
from loguru import logger

from vshift.application.common.logging_config import configure_logging
from vshift.application.server.application_context import ServerApplicationContext
from vshift.infrastructure.api import create_app


def main() -> None:
    context = ServerApplicationContext()
    configure_logging(context.settings)
    context.log_settings()

    api = context.settings.api
    base_url = f"http://{api.host}:{api.port}"
    if api.docs_enabled:
        logger.info("Swagger UI available at {}{}", base_url, api.docs_url)
        logger.info("ReDoc available at {}{}", base_url, api.redoc_url)
        logger.info("OpenAPI spec available at {}{}", base_url, api.openapi_url)

    uvicorn.run(
        create_app(context),
        host=api.host,
        port=api.port,
        log_level=context.settings.logging.level.lower(),
    )


if __name__ == "__main__":
    main()
