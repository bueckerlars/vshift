from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True, slots=True)
class RedisKeys:
    prefix: str

    @property
    def pending_queue(self) -> str:
        return f"{self.prefix}:queue:pending"

    @property
    def dead_letter_queue(self) -> str:
        return f"{self.prefix}:dlq"

    def job(self, job_id: UUID) -> str:
        return f"{self.prefix}:job:{job_id}"

    def job_summary(self, job_id: UUID) -> str:
        return f"{self.prefix}:job:{job_id}:summary"

    def job_heartbeat(self, job_id: UUID) -> str:
        return f"{self.prefix}:job:{job_id}:heartbeat"

    def job_state_index(self, state: str) -> str:
        return f"{self.prefix}:jobs:state:{state}"

    def worker(self, worker_id: UUID) -> str:
        return f"{self.prefix}:workers:{worker_id}"

    @property
    def workers_index(self) -> str:
        return f"{self.prefix}:workers:index"

    def processed_file(self, canonical_path: str) -> str:
        return f"{self.prefix}:processed:{canonical_path}"
