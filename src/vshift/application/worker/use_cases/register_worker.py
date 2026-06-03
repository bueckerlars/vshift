import platform
import socket
import sys
from datetime import UTC, datetime
from uuid import UUID

from loguru import logger

from vshift.domain.worker.worker_capabilities import WorkerCapabilities
from vshift.domain.worker.worker_hardware_info import WorkerHardwareInfo
from vshift.domain.worker.worker_info import WorkerInfo, WorkerStatus
from vshift.infrastructure.ffmpeg.encoder_resolver import EncoderResolver
from vshift.infrastructure.ffmpeg.version import ffmpeg_version
from vshift.ports.worker_registry import WorkerRegistry


class RegisterWorker:
    """Registers this worker process in the worker registry."""

    def __init__(
        self,
        worker_registry: WorkerRegistry,
        encoder_resolver: EncoderResolver,
        *,
        worker_id: UUID,
        ffmpeg_path: str = "ffmpeg",
    ) -> None:
        self._worker_registry = worker_registry
        self._encoder_resolver = encoder_resolver
        self._worker_id = worker_id
        self._ffmpeg_path = ffmpeg_path

    def execute(self) -> WorkerInfo:
        now = datetime.now(tz=UTC)
        worker = WorkerInfo(
            worker_id=self._worker_id,
            hostname=socket.gethostname(),
            created_at=now,
            last_seen_at=now,
            status=WorkerStatus.IDLE,
            capabilities=WorkerCapabilities(
                ffmpeg_version=ffmpeg_version(self._ffmpeg_path),
                encoders=sorted(self._encoder_resolver.list_available_encoders()),
            ),
            hardware=WorkerHardwareInfo(
                platform=sys.platform,
                architecture=platform.machine(),
            ),
        )
        self._worker_registry.register(worker)
        logger.info("registered worker {} on {}", worker.worker_id, worker.hostname)
        return worker
