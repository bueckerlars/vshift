from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel

from vshift.domain.worker.worker_capabilities import WorkerCapabilities
from vshift.domain.worker.worker_hardware_info import WorkerHardwareInfo


class WorkerStatus(StrEnum):
    IDLE = "idle"
    BUSY = "busy"
    DRAINING = "draining"


class WorkerInfo(BaseModel):
    worker_id: UUID
    hostname: str
    created_at: datetime
    last_seen_at: datetime
    status: WorkerStatus
    capabilities: WorkerCapabilities
    hardware: WorkerHardwareInfo
