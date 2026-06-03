from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import fakeredis
import pytest

from vshift.application.server.use_cases.enqueue_job import EnqueueJob
from vshift.application.server.use_cases.models import ProfileMatch
from vshift.application.worker.use_cases.claim_job import ClaimJob
from vshift.application.worker.use_cases.execute_transcode import ExecuteTranscode
from vshift.application.worker.use_cases.handle_job_failure import HandleJobFailure
from vshift.application.worker.use_cases.process_next_job import ProcessNextJob
from vshift.application.worker.use_cases.register_worker import RegisterWorker
from vshift.application.worker.use_cases.write_summary import WriteSummary
from vshift.domain.file.probed_input import ProbedInput
from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding.transcode_result import TranscodeResult
from vshift.domain.transcoding_profile import VshiftProfile
from vshift.exception import VShiftException
from vshift.infrastructure.ffmpeg.encoder_resolver import EncoderResolver
from vshift.infrastructure.filesystem.yaml_config_repository import YamlConfigRepository
from vshift.infrastructure.redis.factory import RedisStores
from vshift.infrastructure.redis.job_store import RedisJobRepository
from vshift.infrastructure.redis.keys import RedisKeys
from vshift.infrastructure.redis.processed_file_store import RedisProcessedFileStore
from vshift.infrastructure.redis.task_queue import RedisTaskQueue
from vshift.infrastructure.redis.worker_registry import RedisWorkerRegistry

WORKER_ID = UUID("00000000-0000-4000-8000-000000000002")


class StubTranscoder:
    def transcode(self, job: TranscodeJob) -> TranscodeResult:
        job.output_path.parent.mkdir(parents=True, exist_ok=True)
        job.output_path.write_bytes(b"output")
        return TranscodeResult(
            output_path=job.output_path,
            wall_clock_seconds=1.5,
            ffmpeg_version="test",
            video_codec_out=job.profile_snapshot.video.codec,
            resolution_out="1920x1080",
        )

    def build_summary(
        self,
        job: TranscodeJob,
        result: TranscodeResult,
    ) -> JobSummary:
        now = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        return JobSummary(
            job_id=job.id,
            input_path=job.input_path,
            output_path=result.output_path,
            profile_name=job.profile_name,
            input_size_bytes=1000,
            output_size_bytes=500,
            input_duration_seconds=60.0,
            compression_ratio=2.0,
            wall_clock_seconds=result.wall_clock_seconds,
            ffmpeg_version=result.ffmpeg_version,
            started_at=now,
            completed_at=now,
            video_codec_in="h264",
            video_codec_out=result.video_codec_out,
            resolution_in="1920x1080",
            resolution_out=result.resolution_out,
        )


class FailingTranscoder:
    def transcode(self, job: TranscodeJob) -> TranscodeResult:
        msg = f"transcode failed for {job.id}"
        raise VShiftException(msg)

    def build_summary(
        self,
        job: TranscodeJob,
        result: TranscodeResult,
    ) -> JobSummary:
        del job, result
        raise VShiftException("should not build summary")


@pytest.fixture
def config_repository(tmp_path: Path) -> YamlConfigRepository:
    input_dir = tmp_path / "input"
    output_dir = tmp_path / "output"
    temp_dir = tmp_path / "temp"
    config_path = tmp_path / "vshift.yaml"
    config_path.write_text(
        f"""
version: "1"

behavior:
  max_retries: 2

directories:
  input: {input_dir}
  output: {output_dir}
  temp: {temp_dir}

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


def _sample_profile() -> VshiftProfile:
    return VshiftProfile.model_validate(
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


def _sample_match() -> ProfileMatch:
    return ProfileMatch(
        rule_id="default",
        profile_name="h264_1080p",
        profile=_sample_profile(),
    )


def _save_processing_job(
    redis_stores: RedisStores,
    *,
    input_path: Path,
    attempt: int = 1,
) -> TranscodeJob:
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"input")
    job = TranscodeJob(
        id=uuid4(),
        input_path=input_path,
        output_path=input_path.with_suffix(".mp4"),
        profile_name="h264_1080p",
        profile_snapshot=_sample_profile(),
        state=JobState.PROCESSING,
        worker_id=WORKER_ID,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        attempt=attempt,
        match_rule_id="default",
    )
    redis_stores.job_repository.save(job)
    return job


def _enqueue_pending_job(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    *,
    input_path: Path,
    attempt: int = 1,
) -> TranscodeJob:
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_bytes(b"input")
    probed = ProbedInput(path=input_path, extension=input_path.suffix.lstrip("."))
    job = EnqueueJob(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        redis_stores.processed_file_store,
    ).execute(probed, _sample_match())
    assert job is not None
    if attempt > 1:
        updated = job.model_copy(update={"attempt": attempt})
        redis_stores.job_repository.save(updated)
        return updated
    return job


def test_register_worker_persists_worker_info(redis_stores: RedisStores) -> None:
    worker = RegisterWorker(
        redis_stores.worker_registry,
        EncoderResolver(available_encoders={"libx264"}),
        worker_id=WORKER_ID,
        ffmpeg_path="ffmpeg",
    ).execute()

    workers = redis_stores.worker_registry.list_workers()
    assert len(workers) == 1
    assert workers[0].worker_id == worker.worker_id
    assert "libx264" in workers[0].capabilities.encoders


def test_claim_job_transitions_pending_job_to_claimed(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    tmp_path: Path,
) -> None:
    job = _enqueue_pending_job(
        config_repository,
        redis_stores,
        input_path=tmp_path / "movie.mkv",
    )
    RegisterWorker(
        redis_stores.worker_registry,
        EncoderResolver(available_encoders={"libx264"}),
        worker_id=WORKER_ID,
    ).execute()

    claimed = ClaimJob(
        redis_stores.job_repository,
        redis_stores.task_queue,
        redis_stores.worker_registry,
        worker_id=WORKER_ID,
        dequeue_timeout_seconds=0,
    ).execute()

    assert claimed is not None
    assert claimed.id == job.id
    assert claimed.state == JobState.CLAIMED
    assert claimed.worker_id == WORKER_ID
    assert redis_stores.worker_registry.is_job_alive(claimed.id)


def test_execute_transcode_and_write_summary_complete_job(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    tmp_path: Path,
) -> None:
    input_path = tmp_path / "movie.mkv"
    job = _enqueue_pending_job(config_repository, redis_stores, input_path=input_path)
    claimed = job.model_copy(
        update={
            "state": JobState.CLAIMED,
            "worker_id": WORKER_ID,
            "claimed_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
    )
    redis_stores.job_repository.save(claimed)

    execution = ExecuteTranscode(
        redis_stores.job_repository,
        redis_stores.worker_registry,
        StubTranscoder(),
        worker_id=WORKER_ID,
    ).execute(claimed)
    summary = WriteSummary(
        redis_stores.job_repository,
        StubTranscoder(),
    ).execute(execution.job, execution.result)

    stored = redis_stores.job_repository.get(job.id)
    assert stored is not None
    assert stored.state == JobState.COMPLETED
    assert redis_stores.job_repository.get_summary(job.id) == summary


def test_handle_job_failure_requeues_when_retries_remain(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    tmp_path: Path,
) -> None:
    job = _save_processing_job(
        redis_stores,
        input_path=tmp_path / "a.mkv",
    )

    updated = HandleJobFailure(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        worker_id=WORKER_ID,
    ).execute(job, "ffmpeg failed")

    assert updated.state == JobState.PENDING
    assert updated.attempt == 2
    assert redis_stores.task_queue.depth() == 1


def test_handle_job_failure_moves_exhausted_job_to_dlq(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    tmp_path: Path,
) -> None:
    job = _save_processing_job(
        redis_stores,
        input_path=tmp_path / "a.mkv",
        attempt=2,
    )

    updated = HandleJobFailure(
        config_repository,
        redis_stores.job_repository,
        redis_stores.task_queue,
        worker_id=WORKER_ID,
    ).execute(job, "ffmpeg failed")

    assert updated.state == JobState.FAILED
    assert redis_stores.task_queue.dead_letter_depth() == 1


def test_process_next_job_runs_full_success_pipeline(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    tmp_path: Path,
) -> None:
    _enqueue_pending_job(
        config_repository,
        redis_stores,
        input_path=tmp_path / "movie.mkv",
    )
    RegisterWorker(
        redis_stores.worker_registry,
        EncoderResolver(available_encoders={"libx264"}),
        worker_id=WORKER_ID,
    ).execute()

    completed = ProcessNextJob(
        ClaimJob(
            redis_stores.job_repository,
            redis_stores.task_queue,
            redis_stores.worker_registry,
            worker_id=WORKER_ID,
            dequeue_timeout_seconds=0,
        ),
        ExecuteTranscode(
            redis_stores.job_repository,
            redis_stores.worker_registry,
            StubTranscoder(),
            worker_id=WORKER_ID,
        ),
        WriteSummary(redis_stores.job_repository, StubTranscoder()),
        HandleJobFailure(
            config_repository,
            redis_stores.job_repository,
            redis_stores.task_queue,
            worker_id=WORKER_ID,
        ),
        redis_stores.job_repository,
    ).execute()

    assert completed is not None
    assert completed.state == JobState.COMPLETED
    assert redis_stores.job_repository.get_summary(completed.id) is not None


def test_process_next_job_handles_transcode_failure(
    config_repository: YamlConfigRepository,
    redis_stores: RedisStores,
    tmp_path: Path,
) -> None:
    job = _enqueue_pending_job(
        config_repository,
        redis_stores,
        input_path=tmp_path / "movie.mkv",
        attempt=2,
    )
    RegisterWorker(
        redis_stores.worker_registry,
        EncoderResolver(available_encoders={"libx264"}),
        worker_id=WORKER_ID,
    ).execute()
    del job

    failed = ProcessNextJob(
        ClaimJob(
            redis_stores.job_repository,
            redis_stores.task_queue,
            redis_stores.worker_registry,
            worker_id=WORKER_ID,
            dequeue_timeout_seconds=0,
        ),
        ExecuteTranscode(
            redis_stores.job_repository,
            redis_stores.worker_registry,
            FailingTranscoder(),
            worker_id=WORKER_ID,
        ),
        WriteSummary(redis_stores.job_repository, FailingTranscoder()),
        HandleJobFailure(
            config_repository,
            redis_stores.job_repository,
            redis_stores.task_queue,
            worker_id=WORKER_ID,
        ),
        redis_stores.job_repository,
    ).execute()

    assert failed is not None
    assert failed.state == JobState.FAILED
    assert redis_stores.task_queue.dead_letter_depth() == 1
