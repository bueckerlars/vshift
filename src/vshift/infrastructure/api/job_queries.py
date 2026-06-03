from vshift.domain.job.job_state import JobState
from vshift.domain.job.transcode_job import TranscodeJob
from vshift.ports.job_repository import JobRepository


def list_jobs(
    repository: JobRepository,
    *,
    state: JobState | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[TranscodeJob]:
    if state is not None:
        return repository.list_by_state(state, limit=limit, offset=offset)

    jobs: list[TranscodeJob] = []
    for job_state in JobState:
        jobs.extend(repository.list_by_state(job_state, limit=1000))

    jobs.sort(key=lambda job: job.created_at, reverse=True)
    return jobs[offset : offset + limit]
