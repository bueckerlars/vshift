# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false, reportIndexIssue=false

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import fakeredis
import pytest
from fastapi.testclient import TestClient

from vshift.application.server.application_context import ServerApplicationContext
from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_summary import JobSummary
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.domain.transcoding_profile import VshiftProfile
from vshift.infrastructure.api import create_app
from vshift.infrastructure.redis.factory import RedisStores
from vshift.infrastructure.redis.job_store import RedisJobRepository
from vshift.infrastructure.redis.keys import RedisKeys
from vshift.infrastructure.redis.processed_file_store import RedisProcessedFileStore
from vshift.infrastructure.redis.task_queue import RedisTaskQueue
from vshift.infrastructure.redis.worker_registry import RedisWorkerRegistry

JOB_ID = UUID("00000000-0000-4000-8000-000000000001")


@pytest.fixture
def redis_stores() -> RedisStores:
    client = fakeredis.FakeRedis(decode_responses=True)
    keys = RedisKeys(prefix="vshift-api-test")
    return RedisStores(
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


@pytest.fixture
def api_client(
    monkeypatch: pytest.MonkeyPatch,
    redis_stores: RedisStores,
) -> Iterator[TestClient]:
    monkeypatch.setenv("VSHIFT__REDIS__PASSWORD", "test")
    context = ServerApplicationContext(redis_stores=redis_stores)
    with TestClient(create_app(context, background_tasks=False)) as test_client:
        yield test_client


def _sample_job() -> TranscodeJob:
    profile = VshiftProfile.model_validate(
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
    return TranscodeJob(
        id=JOB_ID,
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="test",
        profile_snapshot=profile,
        state=JobState.COMPLETED,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        match_rule_id="default",
    )


def _sample_summary() -> JobSummary:
    return JobSummary(
        job_id=JOB_ID,
        input_path=Path("/data/input/movie.mkv"),
        output_path=Path("/data/output/movie.mp4"),
        profile_name="test",
        input_size_bytes=1000,
        output_size_bytes=500,
        input_duration_seconds=60.0,
        compression_ratio=2.0,
        wall_clock_seconds=10.0,
        ffmpeg_version="8.0",
        started_at=datetime(2026, 1, 1, tzinfo=UTC),
        completed_at=datetime(2026, 1, 1, 1, 0, tzinfo=UTC),
        video_codec_in="h264",
        video_codec_out="h264",
        resolution_in="1920x1080",
        resolution_out="1920x1080",
    )


def test_health_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["redis"] == "ok"
    assert payload["version"]


def test_list_jobs_endpoint(
    api_client: TestClient,
    redis_stores: RedisStores,
) -> None:
    redis_stores.job_repository.save(_sample_job())

    response = api_client.get("/jobs")

    assert response.status_code == 200
    jobs = response.json()
    assert len(jobs) == 1
    assert jobs[0]["id"] == str(JOB_ID)
    assert jobs[0]["state"] == "completed"


def test_get_job_endpoint(
    api_client: TestClient,
    redis_stores: RedisStores,
) -> None:
    redis_stores.job_repository.save(_sample_job())

    response = api_client.get(f"/jobs/{JOB_ID}")

    assert response.status_code == 200
    assert response.json()["profile_name"] == "test"


def test_get_job_returns_404_for_missing_job(api_client: TestClient) -> None:
    response = api_client.get(f"/jobs/{JOB_ID}")

    assert response.status_code == 404


def test_get_job_summary_endpoint(
    api_client: TestClient,
    redis_stores: RedisStores,
) -> None:
    redis_stores.job_repository.save(_sample_job())
    redis_stores.job_repository.save_summary(_sample_summary())

    response = api_client.get(f"/jobs/{JOB_ID}/summary")

    assert response.status_code == 200
    assert response.json()["compression_ratio"] == 2.0


def test_openapi_spec_is_available(api_client: TestClient) -> None:
    response = api_client.get("/openapi.json")

    assert response.status_code == 200
    spec = response.json()
    assert spec["info"]["title"] == "vshift"
    assert spec["info"]["version"]
    assert "/health" in spec["paths"]
    assert "/jobs" in spec["paths"]
    assert "/jobs/{job_id}" in spec["paths"]
    assert "/jobs/{job_id}/summary" in spec["paths"]


def test_swagger_ui_is_available(api_client: TestClient) -> None:
    response = api_client.get("/docs")

    assert response.status_code == 200
    assert "swagger-ui" in response.text


def test_redoc_is_available(api_client: TestClient) -> None:
    response = api_client.get("/redoc")

    assert response.status_code == 200
    assert "redoc" in response.text.lower()
