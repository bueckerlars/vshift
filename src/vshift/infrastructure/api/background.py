from threading import Event, Thread

from loguru import logger

from vshift.application.server.application_context import ServerApplicationContext


def start_background_threads(
    context: ServerApplicationContext,
    stop_event: Event,
) -> list[Thread]:
    threads: list[Thread] = []

    scan_thread = Thread(
        target=_run_scan_loop,
        args=(context, stop_event, context.settings.server.scan_interval_seconds),
        name="vshift-scan",
        daemon=True,
    )
    recovery_thread = Thread(
        target=_run_recovery_loop,
        args=(
            context,
            stop_event,
            context.settings.server.recovery_interval_seconds,
        ),
        name="vshift-recovery",
        daemon=True,
    )
    scan_thread.start()
    recovery_thread.start()
    threads.extend([scan_thread, recovery_thread])

    if context.settings.kubernetes.enabled:
        scale_thread = Thread(
            target=_run_worker_scale_loop,
            args=(
                context,
                stop_event,
                context.settings.server.worker_scale_interval_seconds,
            ),
            name="vshift-worker-scale",
            daemon=True,
        )
        scale_thread.start()
        threads.append(scale_thread)

    return threads


def _run_scan_loop(
    context: ServerApplicationContext,
    stop_event: Event,
    interval_seconds: int,
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            context.scan_input_folder.execute()
        except Exception:
            logger.exception("input scan failed")


def _run_recovery_loop(
    context: ServerApplicationContext,
    stop_event: Event,
    interval_seconds: int,
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            context.recover_stale_jobs.execute()
        except Exception:
            logger.exception("stale job recovery failed")


def _run_worker_scale_loop(
    context: ServerApplicationContext,
    stop_event: Event,
    interval_seconds: int,
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            context.ensure_worker_capacity.execute()
        except Exception:
            logger.exception("worker scaling failed")
