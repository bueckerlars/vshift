from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from vshift.domain.job.job_state import JobState
from vshift.infrastructure.api.dependencies import JobRepositoryDep
from vshift.infrastructure.api.job_queries import list_jobs
from vshift.infrastructure.api.mappers import job_to_response
from vshift.infrastructure.api.schemas import JobResponse, JobSummaryResponse

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get(
    "",
    response_model=list[JobResponse],
    summary="List jobs",
    description="Returns transcoding jobs ordered by creation time (newest first).",
)
def get_jobs(
    repository: JobRepositoryDep,
    state: Annotated[
        JobState | None,
        Query(description="Filter by job state"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=500, description="Maximum results")] = 100,
    offset: Annotated[int, Query(ge=0, description="Pagination offset")] = 0,
) -> list[JobResponse]:
    jobs = list_jobs(repository, state=state, limit=limit, offset=offset)
    return [job_to_response(job) for job in jobs]


@router.get(
    "/{job_id}",
    response_model=JobResponse,
    summary="Get job",
    description="Returns a single job by ID.",
    responses={404: {"description": "Job not found"}},
)
def get_job(job_id: UUID, repository: JobRepositoryDep) -> JobResponse:
    job = repository.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job not found")
    return job_to_response(job)


@router.get(
    "/{job_id}/summary",
    response_model=JobSummaryResponse,
    summary="Get job summary",
    description="Returns transcoding statistics for a completed job.",
    responses={404: {"description": "Job summary not found"}},
)
def get_job_summary(job_id: UUID, repository: JobRepositoryDep) -> JobSummaryResponse:
    summary = repository.get_summary(job_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="job summary not found")
    return JobSummaryResponse.model_validate(summary, from_attributes=True)
