from __future__ import annotations

from cog_trace.core.graph import CognitiveGraph
from cog_trace.core.schema import CreditEvent, EvidenceRelation, StateTransition


class StateMachine:
    """Apply only verified evidence relations to grounded state."""

    def apply_relation(
        self, graph: CognitiveGraph, relation: EvidenceRelation
    ) -> tuple[StateTransition | None, CreditEvent | None]:
        if relation.verification != "verified":
            return None, None
        target = graph.nodes[relation.target_id]
        old_status = target.status
        new_status = old_status
        credit: CreditEvent | None = None

        if target.kind == "claim":
            evidence = graph.nodes[relation.evidence_id]
            if (
                relation.relation == "supports"
                and old_status == "active"
                and evidence.metadata.get("test_passed") is True
                and relation.metadata.get("acceptance_test") is True
            ):
                new_status = "accepted"
            elif relation.relation == "supports" and old_status in {
                "candidate",
                "refuted",
            }:
                new_status = "active"
                event_type = (
                    "successful_hypothesis_switch"
                    if old_status == "refuted"
                    else "informative_evidence"
                )
                credit = CreditEvent(
                    step_id=relation.step_id,
                    type=event_type,
                    polarity="positive",
                    confidence=1.0,
                    node_ids=[target.node_id],
                    evidence_ids=[relation.evidence_id],
                )
            elif relation.relation == "contradicts" and old_status in {"candidate", "active"}:
                new_status = "refuted"
                credit = CreditEvent(
                    step_id=relation.step_id,
                    type="correct_claim_revision",
                    polarity="positive",
                    confidence=1.0,
                    node_ids=[target.node_id],
                    evidence_ids=[relation.evidence_id],
                )
        elif target.kind == "constraint":
            if relation.relation == "satisfies" and old_status == "unresolved":
                new_status = "satisfied"
                credit = CreditEvent(
                    step_id=relation.step_id,
                    type="constraint_satisfied",
                    polarity="positive",
                    confidence=1.0,
                    node_ids=[target.node_id],
                    evidence_ids=[relation.evidence_id],
                )
            elif relation.relation == "violates":
                new_status = "violated"

        if new_status == old_status:
            return None, credit
        graph.set_status(target.node_id, new_status, relation.step_id)
        transition = StateTransition(
            node_id=target.node_id,
            from_status=old_status,
            to_status=new_status,
            step_id=relation.step_id,
            cause_relation_id=relation.relation_id,
        )
        return transition, credit
