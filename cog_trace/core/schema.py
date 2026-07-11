from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Literal

EventType = Literal["issue", "thought", "action", "observation", "test", "diff", "finish"]
NodeKind = Literal["goal", "constraint", "claim", "evidence", "decision", "action"]
RelationType = Literal["supports", "contradicts", "satisfies", "violates", "justifies"]
VerificationStatus = Literal["proposed", "verified", "rejected"]

NODE_TYPES = {"Goal", "Constraint", "Claim", "Evidence", "Decision", "Action"}
EDGE_TYPES = {"supports", "contradicts", "satisfies", "violates", "justifies"}
NODE_STATUSES = {
    "candidate",
    "active",
    "refuted",
    "accepted",
    "unresolved",
    "satisfied",
    "violated",
    "planned",
    "executed",
    "superseded",
    "observed",
}


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class ActionKind(Enum):
    READ_FILE = "read_file"
    EDIT_FILE = "edit_file"
    RUN_TEST = "run_test"
    RUN_OTHER = "run_other"
    FINISH = "finish"
    OTHER = "other"


@dataclass(frozen=True)
class NormalizedEvent:
    event_id: str
    step_id: int
    type: EventType
    raw_text: str
    files: tuple[str, ...] = ()
    command: str = ""
    tool_name: str = ""
    exit_code: int | None = None
    test_passed: bool | None = None
    test_failed: bool | None = None
    is_environment_error: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    content_hash: str = ""

    def __post_init__(self) -> None:
        if not self.event_id:
            raise ValueError("event_id is required")
        if self.step_id < 0:
            raise ValueError("step_id must be non-negative")
        if not self.content_hash:
            object.__setattr__(self, "content_hash", content_hash(self.raw_text))

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["files"] = list(self.files)
        return data


@dataclass(frozen=True)
class Provenance:
    event_id: str
    exact_span: str
    span_start: int
    span_end: int
    content_hash: str

    @classmethod
    def whole_event(cls, event: NormalizedEvent) -> "Provenance":
        return cls(
            event_id=event.event_id,
            exact_span=event.raw_text,
            span_start=0,
            span_end=len(event.raw_text),
            content_hash=event.content_hash,
        )

    def validate(self, event: NormalizedEvent) -> None:
        if self.event_id != event.event_id:
            raise ValueError("provenance event_id does not match event")
        if self.content_hash != event.content_hash:
            raise ValueError("provenance content hash does not match event")
        if self.span_start < 0 or self.span_end < self.span_start:
            raise ValueError("invalid provenance offsets")
        if self.span_end > len(event.raw_text):
            raise ValueError("provenance span is out of bounds")
        if event.raw_text[self.span_start : self.span_end] != self.exact_span:
            raise ValueError("provenance exact_span is not an exact event substring")


@dataclass
class GroundedNode:
    kind: NodeKind
    canonical_text: str
    provenance: Provenance
    status: str
    confidence: float = 1.0
    node_id: str = ""
    created_step: int = 0
    updated_step: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def id(self) -> str:
        return self.node_id

    @id.setter
    def id(self, value: str) -> None:
        self.node_id = value

    @property
    def type(self) -> str:
        return "Claim" if self.kind == "claim" else self.kind.title()

    @property
    def text(self) -> str:
        return self.canonical_text

    @property
    def source_event(self) -> int:
        return self.created_step

    @property
    def created_at(self) -> int:
        return self.created_step

    @created_at.setter
    def created_at(self, value: int) -> None:
        self.created_step = value

    @property
    def updated_at(self) -> int:
        return self.updated_step

    @updated_at.setter
    def updated_at(self, value: int) -> None:
        self.updated_step = value

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "kind": self.kind,
            "canonical_text": self.canonical_text,
            "status": self.status,
            "confidence": self.confidence,
            "provenance": asdict(self.provenance),
            "created_step": self.created_step,
            "updated_step": self.updated_step,
            "metadata": self.metadata,
        }


@dataclass
class EvidenceRelation:
    evidence_id: str
    target_id: str
    relation: RelationType
    verification: VerificationStatus
    verifier_type: Literal["deterministic", "semantic"]
    step_id: int
    relation_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source(self) -> str:
        return self.evidence_id

    @property
    def target(self) -> str:
        return self.target_id

    @property
    def type(self) -> str:
        return self.relation

    @property
    def source_event(self) -> int:
        return self.step_id

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StateTransition:
    node_id: str
    from_status: str
    to_status: str
    step_id: int
    cause_relation_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CreditEvent:
    step_id: int
    type: str
    polarity: Literal["positive", "negative"]
    confidence: float
    node_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    action_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GuardDecision:
    kind: str
    should_block: bool
    message: str
    step_id: int
    severity: Literal["info", "warning", "error"] = "warning"
    related_node_ids: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessResult:
    nodes_added: list[str] = field(default_factory=list)
    relations_added: list[str] = field(default_factory=list)
    state_transitions: list[StateTransition] = field(default_factory=list)
    credit_events: list[CreditEvent] = field(default_factory=list)
    context_dirty: bool = False
    guard_decision: GuardDecision | None = None
    extraction_requested: bool = False
    extraction_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes_added": self.nodes_added,
            "relations_added": self.relations_added,
            "state_transitions": [item.to_dict() for item in self.state_transitions],
            "credit_events": [item.to_dict() for item in self.credit_events],
            "context_dirty": self.context_dirty,
            "guard_decision": self.guard_decision.to_dict() if self.guard_decision else None,
            "extraction_requested": self.extraction_requested,
            "extraction_reasons": self.extraction_reasons,
        }


@dataclass
class StateSnapshot:
    step_id: int
    active_claims: list[dict[str, Any]] = field(default_factory=list)
    refuted_claims: list[dict[str, Any]] = field(default_factory=list)
    unresolved_constraints: list[dict[str, Any]] = field(default_factory=list)
    verified_evidence: list[dict[str, Any]] = field(default_factory=list)
    pending_decisions: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ContextPack:
    recent_events: list[str] = field(default_factory=list)
    goals: list[dict[str, Any]] = field(default_factory=list)
    unresolved_constraints: list[dict[str, Any]] = field(default_factory=list)
    active_claims: list[dict[str, Any]] = field(default_factory=list)
    refuted_claims: list[dict[str, Any]] = field(default_factory=list)
    verified_evidence: list[dict[str, Any]] = field(default_factory=list)
    pending_decisions: list[dict[str, Any]] = field(default_factory=list)
    token_budget: int = 4096
    estimated_tokens: int = 0

    # Compatibility accessors for the V1 renderer.
    @property
    def goal(self) -> str:
        return self.goals[0]["text"] if self.goals else ""

    @property
    def constraints(self) -> list[str]:
        return [item["text"] for item in self.unresolved_constraints]

    @property
    def active_hypotheses(self) -> list[dict[str, Any]]:
        return self.active_claims + self.refuted_claims

    @property
    def recent_evidence(self) -> list[dict[str, Any]]:
        return self.verified_evidence


@dataclass
class TraceStep:
    event_index: int
    kind: str = ""
    source: str = ""
    tool_name: str = ""
    thought: str = ""
    action_command: str = ""
    action_path: str = ""
    observation: str = ""
    message: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def text(self) -> str:
        parts = [self.message, self.thought, self.observation]
        return "\n".join(part for part in parts if part)


# Lightweight V1 compatibility types. New code should use the grounded types above.
@dataclass
class EventMetadata:
    event_index: int
    action_kind: ActionKind
    files_touched: list[str] = field(default_factory=list)
    command: str = ""
    exit_code: int | None = None
    raw_text: str = ""
    test_passed: bool | None = None
    test_failed: bool | None = None
    is_env_error: bool | None = None
    diff_summary: str = ""


@dataclass
class StructuredReport:
    hypothesis: str = ""
    next_step: str = ""
    confidence: str = ""
    raw: str = ""

    @property
    def confidence_float(self) -> float | None:
        return {"low": 0.30, "medium": 0.60, "high": 0.85}.get(self.confidence)


@dataclass
class GuardMessage:
    kind: str
    text: str
    source_event: int
    severity: str = "info"


CognitiveNode = GroundedNode
CognitiveEdge = EvidenceRelation
NodeType = str
EdgeType = str
NodeStatus = str
