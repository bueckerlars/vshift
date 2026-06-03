from vshift.domain.job.job_state import JobState
from vshift.exception import VShiftException

_VALID_TRANSITIONS: dict[JobState, frozenset[JobState]] = {
    JobState.PENDING: frozenset({JobState.CLAIMED, JobState.FAILED}),
    JobState.CLAIMED: frozenset(
        {JobState.PROCESSING, JobState.PENDING, JobState.FAILED}
    ),
    JobState.PROCESSING: frozenset(
        {JobState.COMPLETED, JobState.PENDING, JobState.FAILED}
    ),
    JobState.COMPLETED: frozenset(),
    JobState.FAILED: frozenset(),
}


class JobStateMachine:
    """Encapsulates valid job state transitions."""

    @staticmethod
    def can_transition(from_state: JobState, to_state: JobState) -> bool:
        return to_state in _VALID_TRANSITIONS[from_state]

    @staticmethod
    def transition(from_state: JobState, to_state: JobState) -> JobState:
        if not JobStateMachine.can_transition(from_state, to_state):
            msg = f"invalid job state transition: {from_state} -> {to_state}"
            raise VShiftException(msg)
        return to_state
