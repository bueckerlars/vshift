from functools import cached_property
from uuid import UUID, uuid4

from vshift.application.common.application_context import ApplicationContext
from vshift.application.worker.use_cases.claim_job import ClaimJob
from vshift.application.worker.use_cases.execute_transcode import ExecuteTranscode
from vshift.application.worker.use_cases.handle_job_failure import HandleJobFailure
from vshift.application.worker.use_cases.process_next_job import ProcessNextJob
from vshift.application.worker.use_cases.register_worker import RegisterWorker
from vshift.application.worker.use_cases.write_summary import WriteSummary
from vshift.infrastructure.ffmpeg.encoder_resolver import EncoderResolver
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.ffmpeg.transcoder import FfmpegTranscoder


class WorkerApplicationContext(ApplicationContext):
    def __init__(self) -> None:
        super().__init__()
        self._worker_id = uuid4()

    @property
    def worker_id(self) -> UUID:
        return self._worker_id

    @cached_property
    def transcoder(self) -> FfmpegTranscoder:
        paths = FfmpegPaths(
            ffmpeg=self.settings.ffmpeg.ffmpeg_path,
            ffprobe=self.settings.ffmpeg.ffprobe_path,
        )
        config = self.config_repository.get_config()
        return FfmpegTranscoder(
            paths=paths,
            temp_dir=config.directories.temp,
            thread_count=self.settings.ffmpeg.thread_count,
        )

    @cached_property
    def encoder_resolver(self) -> EncoderResolver:
        paths = FfmpegPaths(
            ffmpeg=self.settings.ffmpeg.ffmpeg_path,
            ffprobe=self.settings.ffmpeg.ffprobe_path,
        )
        return EncoderResolver(paths)

    @cached_property
    def register_worker(self) -> RegisterWorker:
        stores = self.redis_stores
        return RegisterWorker(
            stores.worker_registry,
            self.encoder_resolver,
            worker_id=self.worker_id,
            ffmpeg_path=self.settings.ffmpeg.ffmpeg_path,
        )

    @cached_property
    def claim_job(self) -> ClaimJob:
        stores = self.redis_stores
        return ClaimJob(
            stores.job_repository,
            stores.task_queue,
            stores.worker_registry,
            worker_id=self.worker_id,
            dequeue_timeout_seconds=self.settings.worker.claim_dequeue_timeout_seconds,
        )

    @cached_property
    def execute_transcode(self) -> ExecuteTranscode:
        stores = self.redis_stores
        return ExecuteTranscode(
            stores.job_repository,
            stores.worker_registry,
            self.transcoder,
            worker_id=self.worker_id,
        )

    @cached_property
    def write_summary(self) -> WriteSummary:
        stores = self.redis_stores
        return WriteSummary(stores.job_repository, self.transcoder)

    @cached_property
    def handle_job_failure(self) -> HandleJobFailure:
        stores = self.redis_stores
        return HandleJobFailure(
            self.config_repository,
            stores.job_repository,
            stores.task_queue,
            worker_id=self.worker_id,
        )

    @cached_property
    def process_next_job(self) -> ProcessNextJob:
        stores = self.redis_stores
        return ProcessNextJob(
            self.claim_job,
            self.execute_transcode,
            self.write_summary,
            self.handle_job_failure,
            stores.job_repository,
        )
