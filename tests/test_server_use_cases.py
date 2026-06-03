import os
import time
from collections.abc import Callable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import fakeredis
import pytest

from vshift.application.server.use_cases.enqueue_job import EnqueueJob
from vshift.application.server.use_cases.match_profile import MatchProfile
from vshift.application.server.use_cases.models import ProfileMatch
from vshift.application.server.use_cases.probe_input_file import ProbeInputFile
from vshift.application.server.use_cases.recover_stale_jobs import RecoverStaleJobs
from vshift.application.server.use_cases.scan_input import ScanInputFolder
from vshift.domain.file.probed_input import ProbedInput
from vshift.domain.job.job_state import JobState
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding_profile import VshiftProfile
from vshift.infrastructure.filesystem.poll_file_scanner import PollFileScanner
from vshift.infrastructure.filesystem.yaml_config_repository import YamlConfigRepository
from vshift.infrastructure.redis.factory import RedisStores
from vshift.infrastructure.redis.job_store import RedisJobRepository
from vshift.infrastructure.redis.keys import RedisKeys
from vshift.infrastructure.redis.processed_file_store import RedisProcessedFileStore
from vshift.infrastructure.redis.task_queue import RedisTaskQueue
from vshift.infrastructure.redis.worker_registry import RedisWorkerRegistry

WORKER_ID = UUID("00000000-0000-4000-8000-000000000002")


class StubMediaProber:
    def __init__(self, *, width: int = 1920, height: int = 1080) -> None:
        self._width = width
        self._height = height

    def probe(self, path: Path) -> ProbedInput:
        return ProbedInput(
            path=path,
            extension=path.suffix.lstrip(".").lower(),
            width=self._width,
            height=self._height,
            duration_seconds=3600.0,
        )


class StubFileScanner:
    def __init__(self, files: list[ProbedInput]) -> None:
        self._files = files

    def start(self, handler: Callable[[ProbedInput], None]) -> None:
        del handler

    def stop(self) -> None:
        return None

    def scan_once(self, input_dir: Path) -> list[ProbedInput]:
        del input_dir
        return list(self._files)


@pytest.fixture
def config_repository(tmp_path: Path) -> YamlConfigRepository:
    config_path = tmp_path / "vshift.yaml"
    config_path.write_text(
        """
version: "1"

behavior:
  no_match: ignore
  file_stability_seconds: 1
  max_retries: 2

directories:
  input: /data/input
  output: /data/output
  temp: /data/temp

profiles:
  h264_1080p:
    name: "H.264 1080p"
    format: mp4
    video:
      codec: h264
      encoder: auto
      quality_mode: constant
      quality: 22.0
      width: 1920
      height: 1080

rules:
  - id: movies_1080p
    priority: 10
    match:
      extensions: [mkv]
      min_width: 1280
    profile: h264_1080p
""",
        encoding="utf-8",
    )
    return YamlConfigRepository(config_path)


@pytest.fixture
def redis_stores() -> Iterator[RedisStores]:
    client = fakeredis.FakeRedis(decode_responses=True)
    keys = RedisKeys(prefix="vshift-test")
    yield RedisStores(
        client=client,
        keys=keys,
        job_repository=RedisJobRepository(client, keys, ttl_seconds=3600),
        task_queue=RedisTaskQueue(client, keys),
        processed_file_store=RedisProcessedFileStore(client, keys),
        worker_registry=RedisWorkerRegistry(
            client,
            keys,
            worker_ttl_seconds=30,
            job_heartbeat_ttl_seconds=60,
        ),
    )


def _sample_match() -> ProfileMatch:
    profile = VshiftProfile.model_validate(
        {
            "name": "H.264 1080p",
            "format": "mp4",
            "video": {
                "codec": "h264",
                "encoder": "auto",
                "quality_mode": "constant",
                "quality": 22.0,
            },
        }
    )
    return ProfileMatch(
        rule_id="movies_1080p",
        profile_name="h264_1080p",
        profile=profile,
    )


def test_poll_file_scanner_returns_stable_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "input"
    input_dir.mkdir()
    stable_file = input_dir / "movie.mkv"
    stable_file.write_bytes(b"stable")
    old_mtime = time.time() - 30
    os.utime(stable_file, (old_mtime, old_mtime))

    unstable_file = input_dir / "copying.mkv"
    unstable_file.write_bytes(b"copying")

    scanner = PollFileScanner(file_stability_seconds=10)
    discovered = scanner.scan_once(input_dir)

    assert len(discovered) == 1
    assert discovered[0].path == stable_file
    assert discovered[0].extension == "mkv"


def test_match_profile_returns_matching_rule(
    config_repository: YamlConfigRepository,
) -> None:
    probed = ProbedInput(
        path=Path("/data/input/movie.mkv"),
        extension="mkv",
        width=1920,
        height=1080,
    )

    match = MatchProfile(config_repository).execute(probed)

    assert match is not None
    assert match.rule_id == "movies_1080p"
    assert match.profile_name == "h264_1080p"


def test_match_profile_uses_default_profile_when_configured(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "default-profile.yaml"
    config_path.write_text(
        """
version: "1"

behavior:
  no_match: default_profile
  default_profile: h264_1080p

directories:
  input: /data/input
  output: /data/output
  temp: /data/temp

profiles:
  h264_1080p:
    name: "H.264 1080p"
    format: mp4
    video:
      codec: h264
      encoder: auto
      quality_mode: constant
      quality: 22.0

rules: []
""",
        encoding="utf-8",
    )
    config_repository = YamlConfigRepository(config_path)
    probed = ProbedInput(
        path=Path("/data/input/other.avi"),
        extension="avi",
        width=640,
        height=480,
    )

    match = MatchProfile(config_repository).execute(probed)

    assert match is not None
    assert match.rule_id == "__default__"
    assert match.profile_name == "h264_1080p"


def test_enqueue_job_persists_and_queues(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
) -> None:
    probed = ProbedInput(
        path=Path("/data/input/movie.mkv"),
        extension="mkv",
        width=1920,
        height=1080,
    )
    use_case = EnqueueJob(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        redis_stores.processed_file_store,
    )

    job = use_case.execute(probed, _sample_match())

    assert job is not None
    assert job.state == JobState.PENDING
    assert job.output_path == Path("/data/output/movie.mp4")
    assert redis_stores.job_repository.get(job.id) == job
    assert redis_stores.task_queue.depth() == 1
    assert redis_stores.processed_file_store.is_processed(probed.path)


def test_enqueue_job_skips_processed_files(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
) -> None:
    probed = ProbedInput(
        path=Path("/data/input/movie.mkv"),
        extension="mkv",
        width=1920,
        height=1080,
    )
    use_case = EnqueueJob(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        redis_stores.processed_file_store,
    )
    first = use_case.execute(probed, _sample_match())
    second = use_case.execute(probed, _sample_match())

    assert first is not None
    assert second is None
    assert redis_stores.task_queue.depth() == 1


def test_scan_input_folder_orchestrates_pipeline(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
) -> None:
    candidate = ProbedInput(
        path=Path("/data/input/movie.mkv"),
        extension="mkv",
    )
    use_case = ScanInputFolder(
        config_repository,
        StubFileScanner([candidate]),
        ProbeInputFile(StubMediaProber()),
        MatchProfile(config_repository),
        EnqueueJob(
            config_repository,
            redis_stores.job_repository,
            redis_stores.task_queue,
            redis_stores.processed_file_store,
        ),
    )

    jobs = use_case.execute(Path("/data/input"))

    assert len(jobs) == 1
    assert jobs[0].profile_name == "h264_1080p"


def test_recover_stale_jobs_requeues_when_retries_remain(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
) -> None:
    job = TranscodeJob(
        id=uuid4(),
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="h264_1080p",
        profile_snapshot=_sample_match().profile,
        state=JobState.CLAIMED,
        worker_id=WORKER_ID,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        claimed_at=datetime(2026, 1, 1, tzinfo=UTC),
        attempt=1,
        match_rule_id="movies_1080p",
    )
    redis_stores.job_repository.save(job)

    recovered = RecoverStaleJobs(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        redis_stores.worker_registry,
    ).execute()

    assert len(recovered) == 1
    assert recovered[0].state == JobState.PENDING
    assert recovered[0].attempt == 2
    assert recovered[0].worker_id is None
    assert redis_stores.task_queue.depth() == 1


def test_recover_stale_jobs_moves_to_dlq_when_retries_exhausted(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
) -> None:
    job = TranscodeJob(
        id=uuid4(),
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="h264_1080p",
        profile_snapshot=_sample_match().profile,
        state=JobState.PROCESSING,
        worker_id=WORKER_ID,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        attempt=2,
        match_rule_id="movies_1080p",
    )
    redis_stores.job_repository.save(job)

    recovered = RecoverStaleJobs(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        redis_stores.worker_registry,
    ).execute()

    assert len(recovered) == 1
    assert recovered[0].state == JobState.FAILED
    assert redis_stores.task_queue.dead_letter_depth() == 1
