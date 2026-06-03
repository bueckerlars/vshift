from vshift.domain.job.transcode_job import TranscodeJob
from vshift.infrastructure.api.schemas import JobResponse


def job_to_response(job: TranscodeJob) -> JobResponse:
    return JobResponse(
        id=job.id,
        input_path=job.input_path,
        output_path=job.output_path,
        profile_name=job.profile_name,
        state=job.state,
        worker_id=job.worker_id,
        created_at=job.created_at,
        claimed_at=job.claimed_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        attempt=job.attempt,
        error_message=job.error_message,
        match_rule_id=job.match_rule_id,
    )
