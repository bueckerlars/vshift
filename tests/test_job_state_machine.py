import pytest

from vshift.domain.job.job_state import JobState
from vshift.domain.job.job_state_machine import JobStateMachine
from vshift.exception import VShiftException


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (JobState.PENDING, JobState.CLAIMED),
        (JobState.CLAIMED, JobState.PROCESSING),
        (JobState.CLAIMED, JobState.PENDING),
        (JobState.PROCESSING, JobState.COMPLETED),
        (JobState.PROCESSING, JobState.PENDING),
        (JobState.PROCESSING, JobState.FAILED),
        (JobState.PENDING, JobState.FAILED),
    ],
)
def test_valid_job_state_transitions(
    from_state: JobState,
    to_state: JobState,
) -> None:
    assert JobStateMachine.can_transition(from_state, to_state)
    assert JobStateMachine.transition(from_state, to_state) == to_state


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        (JobState.PENDING, JobState.COMPLETED),
        (JobState.COMPLETED, JobState.PENDING),
        (JobState.FAILED, JobState.PENDING),
        (JobState.CLAIMED, JobState.COMPLETED),
    ],
)
def test_invalid_job_state_transitions(
    from_state: JobState,
    to_state: JobState,
) -> None:
    assert not JobStateMachine.can_transition(from_state, to_state)
    with pytest.raises(VShiftException):
        JobStateMachine.transition(from_state, to_state)
