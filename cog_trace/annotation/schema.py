from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from cog_trace.core.schema import NormalizedEvent, Provenance

FAILURE_LABELS = {
    "ineffective_patch",
    "unsupported_patch",
    "repeated_exploration",
    "continued_after_refutation",
    "premature_finish",
}


@dataclass
class AnnotatedClaim:
    claim_id: str
    text: str
    provenance: Provenance
    status_before: str
    status_after: str
    certainty: str


@dataclass
class AnnotatedEvidence:
    evidence_id: str
    text: str
    provenance: Provenance
    relation: str
    target_claim_id: str


@dataclass
class AnnotationWindow:
    trajectory_id: str
    repository: str
    start_step: int
    end_step: int
    event_ids: list[str]
    claims: list[AnnotatedClaim] = field(default_factory=list)
    evidence: list[AnnotatedEvidence] = field(default_factory=list)
    action_claim_links: list[dict[str, str]] = field(default_factory=list)
    failure_labels: list[str] = field(default_factory=list)
    abstained_kinds: list[str] = field(default_factory=list)
    annotator_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def validate(self, events: dict[str, NormalizedEvent]) -> None:
        if self.start_step > self.end_step:
            raise ValueError("window start_step must not exceed end_step")
        if not set(self.failure_labels) <= FAILURE_LABELS:
            raise ValueError("annotation contains an unknown failure label")
        for event_id in self.event_ids:
            if event_id not in events:
                raise ValueError(f"annotation references unknown event: {event_id}")
        claim_ids = {claim.claim_id for claim in self.claims}
        for claim in self.claims:
            claim.provenance.validate(events[claim.provenance.event_id])
        for item in self.evidence:
            item.provenance.validate(events[item.provenance.event_id])
            if item.target_claim_id and item.target_claim_id not in claim_ids:
                raise ValueError("evidence targets an unknown claim")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
