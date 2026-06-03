import signal
from threading import Event

from loguru import logger

from vshift.application.common.logging_config import configure_logging
from vshift.application.worker.application_context import WorkerApplicationContext


def main() -> None:
    context = WorkerApplicationContext()
    configure_logging(context.settings)
    context.log_settings()

    stop_event = Event()

    def _handle_stop(*_args: object) -> None:
        logger.info("shutdown signal received")
        stop_event.set()

    signal.signal(signal.SIGINT, _handle_stop)
    signal.signal(signal.SIGTERM, _handle_stop)

    context.register_worker.execute()

    if context.settings.worker.one_shot:
        logger.info("starting one-shot vshift worker {}", context.worker_id)
        context.process_next_job.execute()
        context.redis_stores.worker_registry.deregister(context.worker_id)
        logger.info("one-shot worker {} finished", context.worker_id)
        return

    idle_sleep = context.settings.worker.idle_sleep_seconds
    logger.info("starting vshift worker {}", context.worker_id)
    while not stop_event.is_set():
        job = context.process_next_job.execute()
        context.redis_stores.worker_registry.heartbeat(context.worker_id)
        if job is None and stop_event.wait(idle_sleep):
            break

    context.redis_stores.worker_registry.deregister(context.worker_id)
    logger.info("worker {} stopped", context.worker_id)


if __name__ == "__main__":
    main()
