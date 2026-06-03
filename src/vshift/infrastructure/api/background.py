from threading import Event, Thread

from loguru import logger

from vshift.application.server.application_context import ServerApplicationContext


def start_background_threads(
    context: ServerApplicationContext,
    stop_event: Event,
) -> list[Thread]:
    scan_interval = context.settings.server.scan_interval_seconds
    recovery_interval = context.settings.server.recovery_interval_seconds

    scan_thread = Thread(
        target=_run_scan_loop,
        args=(context, stop_event, scan_interval),
        name="vshift-scan",
        daemon=True,
    )
    recovery_thread = Thread(
        target=_run_recovery_loop,
        args=(context, stop_event, recovery_interval),
        name="vshift-recovery",
        daemon=True,
    )
    scan_thread.start()
    recovery_thread.start()
    return [scan_thread, recovery_thread]


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
