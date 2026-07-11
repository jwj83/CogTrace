from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FailureState:
    trajectory_id: str
    repository: str
    step_id: int
    failure_type: str
    state_snapshot: dict[str, Any]
    student_action: dict[str, Any]
    evidence_event_ids: list[str]
    confidence: float
    task_source: str

    def validate_for_training(self) -> None:
        if self.task_source.lower() in {"swe-bench_verified", "swe-bench_pro"}:
            raise ValueError("evaluation tasks must not be used for OPD training")
        if not 0 <= self.confidence <= 1:
            raise ValueError("failure-state confidence must be in [0, 1]")


@dataclass
class TeacherCorrection:
    claim_revision: dict[str, Any]
    new_active_claim: dict[str, Any] | None
    next_actions: list[dict[str, Any]]
    response_text: str
    top_k_logprobs: list[dict[str, float]] = field(default_factory=list)
    teacher_model: str = ""


@dataclass
class OPDExample:
    failure_state: FailureState
    student_continuation: str
    teacher: TeacherCorrection
    objective: str
    iteration: int

    def validate(self) -> None:
        self.failure_state.validate_for_training()
        if self.objective not in {"sft", "dpo", "reverse_kl"}:
            raise ValueError("objective must be sft, dpo, or reverse_kl")
        if self.objective == "reverse_kl" and not self.teacher.top_k_logprobs:
            raise ValueError("strict OPD requires teacher token distributions")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
