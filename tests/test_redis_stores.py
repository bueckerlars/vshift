from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import fakeredis
import pytest

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding_profile import VshiftProfile
from vshift.domain.worker.worker_capabilities import WorkerCapabilities
from vshift.domain.worker.worker_hardware_info import WorkerHardwareInfo
from vshift.domain.worker.worker_info import WorkerInfo, WorkerStatus
from vshift.infrastructure.redis.factory import RedisStores
from vshift.infrastructure.redis.job_store import RedisJobRepository
from vshift.infrastructure.redis.keys import RedisKeys
from vshift.infrastructure.redis.processed_file_store import RedisProcessedFileStore
from vshift.infrastructure.redis.task_queue import RedisTaskQueue
from vshift.infrastructure.redis.worker_registry import RedisWorkerRegistry

JOB_ID = UUID("00000000-0000-4000-8000-000000000001")
WORKER_ID = UUID("00000000-0000-4000-8000-000000000002")


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
            "name": "Test",
            "format": "mp4",
            "video": {
                "codec": "h264",
                "encoder": "auto",
                "quality_mode": "constant",
                "quality": 22.0,
            },
        }
    )


def _sample_job(
    *,
    job_id: UUID = JOB_ID,
    state: JobState = JobState.PENDING,
) -> TranscodeJob:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return TranscodeJob(
        id=job_id,
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="test",
        profile_snapshot=_sample_profile(),
        state=state,
        created_at=now,
        match_rule_id="default",
    )


def test_redis_job_repository_save_and_get(redis_stores: RedisStores) -> None:
    job = _sample_job()
    redis_stores.job_repository.save(job)

    loaded = redis_stores.job_repository.get(JOB_ID)
    assert loaded is not None
    assert loaded.state == JobState.PENDING
    assert loaded.profile_name == "test"


def test_redis_job_repository_lists_by_state(redis_stores: RedisStores) -> None:
    pending = _sample_job(
        job_id=UUID("00000000-0000-4000-8000-000000000010"),
        state=JobState.PENDING,
    )
    completed = _sample_job(
        job_id=UUID("00000000-0000-4000-8000-000000000011"),
        state=JobState.COMPLETED,
    )
    redis_stores.job_repository.save(pending)
    redis_stores.job_repository.save(completed)

    pending_jobs = redis_stores.job_repository.list_by_state(JobState.PENDING)
    completed_jobs = redis_stores.job_repository.list_by_state(JobState.COMPLETED)

    assert len(pending_jobs) == 1
    assert pending_jobs[0].state == JobState.PENDING
    assert len(completed_jobs) == 1
    assert completed_jobs[0].state == JobState.COMPLETED


def test_redis_job_repository_summary_roundtrip(redis_stores: RedisStores) -> None:
    summary = JobSummary(
        job_id=JOB_ID,
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="test",
        input_size_bytes=1_000,
        output_size_bytes=500,
        wall_clock_seconds=12.5,
        ffmpeg_version="7.0",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 0, 1, tzinfo=UTC),
        video_codec_out="h264",
    )
    redis_stores.job_repository.save_summary(summary)

    loaded = redis_stores.job_repository.get_summary(JOB_ID)
    assert loaded is not None
    assert loaded.output_size_bytes == 500


def test_redis_task_queue_fifo_and_requeue(redis_stores: RedisStores) -> None:
    first = uuid4()
    second = uuid4()
    redis_stores.task_queue.enqueue(first)
    redis_stores.task_queue.enqueue(second)

    assert redis_stores.task_queue.depth() == 2
    assert redis_stores.task_queue.dequeue() == first
    assert redis_stores.task_queue.dequeue() == second
    assert redis_stores.task_queue.dequeue() is None

    redis_stores.task_queue.requeue(first)
    assert redis_stores.task_queue.dequeue() == first


def test_redis_task_queue_dead_letter_queue(redis_stores: RedisStores) -> None:
    redis_stores.task_queue.push_to_dead_letter(JOB_ID)
    assert redis_stores.task_queue.dead_letter_depth() == 1


def test_redis_processed_file_store(redis_stores: RedisStores) -> None:
    input_path = Path("/data/input/movie.mkv")
    assert not redis_stores.processed_file_store.is_processed(input_path)
    redis_stores.processed_file_store.mark_processed(input_path, JOB_ID)
    assert redis_stores.processed_file_store.is_processed(input_path)


def test_redis_worker_registry_and_job_heartbeat(redis_stores: RedisStores) -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    worker = WorkerInfo(
        worker_id=WORKER_ID,
        hostname="worker-1",
        created_at=now,
        last_seen_at=now,
        status=WorkerStatus.IDLE,
        capabilities=WorkerCapabilities(
            ffmpeg_version="7.0",
            encoders=["libx264"],
        ),
        hardware=WorkerHardwareInfo(
            platform="linux",
            architecture="x86_64",
        ),
    )
    redis_stores.worker_registry.register(worker)
    workers = redis_stores.worker_registry.list_workers()
    assert len(workers) == 1
    assert workers[0].worker_id == WORKER_ID

    redis_stores.worker_registry.set_job_heartbeat(JOB_ID, WORKER_ID)
    assert redis_stores.worker_registry.is_job_alive(JOB_ID)

    redis_stores.worker_registry.deregister(WORKER_ID)
    assert redis_stores.worker_registry.list_workers() == []
