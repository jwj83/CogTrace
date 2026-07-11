from __future__ import annotations

import pytest

from cog_trace.opd.schema import FailureState, OPDExample, TeacherCorrection


def _failure(source: str = "swe-smith") -> FailureState:
    return FailureState(
        trajectory_id="t1",
        repository="example",
        step_id=12,
        failure_type="continued_after_refutation",
        state_snapshot={},
        student_action={"tool": "edit"},
        evidence_event_ids=["e1"],
        confidence=0.95,
        task_source=source,
    )


def test_evaluation_tasks_are_rejected_for_training() -> None:
    with pytest.raises(ValueError, match="must not"):
        _failure("SWE-bench_Pro").validate_for_training()


def test_strict_opd_requires_teacher_distribution() -> None:
    example = OPDExample(
        failure_state=_failure(),
        student_continuation="keep editing parser.py",
        teacher=TeacherCorrection({}, None, [], "revise the claim"),
        objective="reverse_kl",
        iteration=1,
    )
    with pytest.raises(ValueError, match="token distributions"):
        example.validate()
