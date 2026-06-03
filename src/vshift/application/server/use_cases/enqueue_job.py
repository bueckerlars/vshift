from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from loguru import logger

from vshift.application.server.use_cases.models import ProfileMatch
from vshift.domain.file.probed_input import ProbedInput
from vshift.domain.job.job_state import JobState
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding_profile.vshift_profile import VshiftProfile
from vshift.ports.config_repository import ConfigRepository
from vshift.ports.job_repository import JobRepository
from vshift.ports.processed_file_store import ProcessedFileStore
from vshift.ports.task_queue import TaskQueue


class EnqueueJob:
    """Creates a pending transcode job and pushes it to the queue."""

    def __init__(
        self,
        config_repository: ConfigRepository,
        job_repository: JobRepository,
        task_queue: TaskQueue,
        processed_file_store: ProcessedFileStore,
    ) -> None:
        self._config_repository = config_repository
        self._job_repository = job_repository
        self._task_queue = task_queue
        self._processed_file_store = processed_file_store

    def execute(
        self,
        probed: ProbedInput,
        match: ProfileMatch,
    ) -> TranscodeJob | None:
        if self._processed_file_store.is_processed(probed.path):
            logger.debug("skipping already processed file: {}", probed.path)
            return None

        config = self._config_repository.get_config()
        job = TranscodeJob(
            id=uuid4(),
            input_path=probed.path,
            output_path=_build_output_path(
                config.directories.output,
                probed.path,
                match.profile,
            ),
            profile_name=match.profile_name,
            profile_snapshot=match.profile,
            state=JobState.PENDING,
            created_at=datetime.now(tz=UTC),
            match_rule_id=match.rule_id,
        )
        self._job_repository.save(job)
        self._processed_file_store.mark_processed(probed.path, job.id)
        self._task_queue.enqueue(job.id)
        logger.info(
            "enqueued job {} for {} using profile {}",
            job.id,
            probed.path,
            match.profile_name,
        )
        return job


def _build_output_path(
    output_dir: Path,
    input_path: Path,
    profile: VshiftProfile,
) -> Path:
    return output_dir / f"{input_path.stem}.{profile.format}"
