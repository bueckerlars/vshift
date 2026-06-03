from functools import cached_property

from vshift.application.common.application_context import ApplicationContext
from vshift.application.server.use_cases.enqueue_job import EnqueueJob
from vshift.application.server.use_cases.match_profile import MatchProfile
from vshift.application.server.use_cases.probe_input_file import ProbeInputFile
from vshift.application.server.use_cases.recover_stale_jobs import RecoverStaleJobs
from vshift.application.server.use_cases.scan_input import ScanInputFolder
from vshift.infrastructure.ffmpeg.media_prober import FfmpegMediaProber
from vshift.infrastructure.ffmpeg.models import FfmpegPaths
from vshift.infrastructure.filesystem.poll_file_scanner import PollFileScanner
from vshift.infrastructure.redis.factory import RedisStores, create_redis_stores


class ServerApplicationContext(ApplicationContext):
    def __init__(self, *, redis_stores: RedisStores | None = None) -> None:
        self._injected_redis_stores = redis_stores
        super().__init__()

    @cached_property
    def redis_stores(self) -> RedisStores:
        if self._injected_redis_stores is not None:
            return self._injected_redis_stores
        return create_redis_stores(self.settings.redis, self.settings.queue)

    @cached_property
    def media_prober(self) -> FfmpegMediaProber:
        paths = FfmpegPaths(
            ffmpeg=self.settings.ffmpeg.ffmpeg_path,
            ffprobe=self.settings.ffmpeg.ffprobe_path,
        )
        return FfmpegMediaProber(paths)

    @cached_property
    def file_scanner(self) -> PollFileScanner:
        return PollFileScanner(
            file_stability_seconds=self.config_repository.get_file_stability_seconds(),
        )

    @cached_property
    def probe_input_file(self) -> ProbeInputFile:
        return ProbeInputFile(self.media_prober)

    @cached_property
    def match_profile(self) -> MatchProfile:
        return MatchProfile(self.config_repository)

    @cached_property
    def enqueue_job(self) -> EnqueueJob:
        stores = self.redis_stores
        return EnqueueJob(
            self.config_repository,
            stores.job_repository,
            stores.task_queue,
            stores.processed_file_store,
        )

    @cached_property
    def scan_input_folder(self) -> ScanInputFolder:
        return ScanInputFolder(
            self.config_repository,
            self.file_scanner,
            self.probe_input_file,
            self.match_profile,
            self.enqueue_job,
        )

    @cached_property
    def recover_stale_jobs(self) -> RecoverStaleJobs:
        stores = self.redis_stores
        return RecoverStaleJobs(
            self.config_repository,
            stores.job_repository,
            stores.task_queue,
            stores.worker_registry,
        )
