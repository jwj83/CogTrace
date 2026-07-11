from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from cog_trace.context.policy import ContextBudget, ContextPacker, render_context_pack
from cog_trace.core.graph import CognitiveGraph
from cog_trace.core.schema import (
    CreditEvent,
    GroundedNode,
    GuardMessage,
    NormalizedEvent,
    ProcessResult,
    Provenance,
    TraceStep,
)
from cog_trace.core.state_machine import StateMachine
from cog_trace.extraction.base import ExtractionBatch, GroundedExtractor
from cog_trace.extraction.policy import ExtractionPolicy
from cog_trace.guards.policy import GuardPolicy
from cog_trace.trajectory.normalize import normalize_trace_step

_GUARD_CREDIT_TYPES = {
    "continued_after_refutation": "continued_after_refutation",
    "repeated_exploration": "repeated_action_without_information_gain",
    "unsupported_patch": "unsupported_patch",
    "premature_finish": "premature_finish",
}


@dataclass
class CogTraceManager:
    graph: CognitiveGraph = field(default_factory=CognitiveGraph)
    extractor: GroundedExtractor | None = None
    extraction_policy: ExtractionPolicy = field(default_factory=ExtractionPolicy)
    state_machine: StateMachine = field(default_factory=StateMachine)
    guard_policy: GuardPolicy = field(default_factory=GuardPolicy)
    context_budget: ContextBudget = field(default_factory=ContextBudget.qwen_128k)
    semantic_guards_enabled: bool = False
    recent_event_limit: int = 256
    step_index: int = 0
    results: list[ProcessResult] = field(default_factory=list)
    credit_events: list[CreditEvent] = field(default_factory=list)
    contradictions: list[GuardMessage] = field(default_factory=list)
    reminders: list[GuardMessage] = field(default_factory=list)
    _recent_events: deque[NormalizedEvent] = field(default_factory=deque)

    def process_event(self, event: NormalizedEvent | TraceStep | Any) -> ProcessResult:
        normalized = self._normalize(event)
        self.step_index = max(self.step_index, normalized.step_id)
        result = ProcessResult()

        if not self.graph.add_event(normalized):
            return result

        guard = self.guard_policy.evaluate(
            normalized,
            self.graph,
            semantic_state_available=self.semantic_guards_enabled and self.extractor is not None,
        )
        if guard is not None:
            result.guard_decision = guard
            credit_type = _GUARD_CREDIT_TYPES.get(guard.kind)
            if credit_type:
                credit = CreditEvent(
                    step_id=normalized.step_id,
                    type=credit_type,
                    polarity="negative",
                    confidence=1.0,
                    node_ids=guard.related_node_ids,
                )
                result.credit_events.append(credit)
                self.credit_events.append(credit)
            legacy = GuardMessage(
                kind=guard.kind,
                text=guard.message,
                source_event=normalized.step_id,
                severity=guard.severity,
            )
            if guard.kind == "continued_after_refutation":
                self.contradictions.append(legacy)
            else:
                self.reminders.append(legacy)

        cheap_nodes = self._add_structured_event_nodes(normalized)
        result.nodes_added.extend(cheap_nodes)
        information_changed = any(
            self.graph.nodes[node_id].kind in {"goal", "constraint", "claim", "evidence"}
            for node_id in cheap_nodes
        )

        should_extract, reasons = self.extraction_policy.observe(normalized)
        if should_extract:
            result.extraction_requested = True
            result.extraction_reasons = reasons
            batch_events = self.extraction_policy.pop_buffer()
            if self.extractor is not None:
                extracted = self.extractor.extract(batch_events)
                extraction_result = self.ingest_extraction(extracted)
                result.nodes_added.extend(extraction_result.nodes_added)
                result.relations_added.extend(extraction_result.relations_added)
                result.state_transitions.extend(extraction_result.state_transitions)
                result.credit_events.extend(extraction_result.credit_events)
                information_changed = information_changed or bool(
                    extraction_result.nodes_added or extraction_result.relations_added
                )

        if information_changed:
            self.guard_policy.note_information_change()
        self.guard_policy.observe(normalized)
        self._recent_events.append(normalized)
        while len(self._recent_events) > self.recent_event_limit:
            self._recent_events.popleft()

        result.context_dirty = bool(
            result.nodes_added
            or result.relations_added
            or result.state_transitions
            or result.guard_decision
        )
        self.credit_events.extend(
            credit for credit in result.credit_events if credit not in self.credit_events
        )
        self.results.append(result)
        return result

    def ingest_extraction(self, batch: ExtractionBatch) -> ProcessResult:
        result = ProcessResult()
        id_map: dict[str, str] = {}
        for node in batch.nodes:
            proposed_id = node.node_id
            before = len(self.graph.nodes)
            node_id = self.graph.add_node(node)
            if proposed_id:
                id_map[proposed_id] = node_id
            if len(self.graph.nodes) > before:
                result.nodes_added.append(node_id)
        for relation in batch.relations:
            relation.evidence_id = id_map.get(relation.evidence_id, relation.evidence_id)
            relation.target_id = id_map.get(relation.target_id, relation.target_id)
            before = len(self.graph.relations)
            relation_id = self.graph.add_relation(relation)
            if len(self.graph.relations) > before:
                result.relations_added.append(relation_id)
            transition, credit = self.state_machine.apply_relation(self.graph, relation)
            if transition:
                result.state_transitions.append(transition)
            if credit:
                result.credit_events.append(credit)
        result.context_dirty = bool(result.nodes_added or result.relations_added)
        return result

    def build_context_pack(self):
        packer = ContextPacker(self.context_budget)
        return packer.pack(self.graph, list(self._recent_events), self.step_index)

    def render(self, include_status_request: bool = False) -> str:
        text = render_context_pack(self.build_context_pack())
        if include_status_request:
            text += (
                "\n\nReport any new claim with an exact source span. If none is explicit, abstain."
            )
        return text

    def snapshot(self):
        return self.graph.snapshot(self.step_index)

    def update(self, step: Any) -> list[str]:
        """V1 compatibility wrapper."""
        result = self.process_event(step)
        actions = ["inject_context_pack"] if result.context_dirty else []
        if result.guard_decision:
            actions.append(f"guard:{result.guard_decision.kind}")
        actions.extend(
            f"state_transition:{item.node_id}->{item.to_status}"
            for item in result.state_transitions
        )
        return actions

    def process_step(self, step: Any, total_events: int | None = None) -> ProcessResult:
        return self.process_event(step)

    def render_guard_messages(self) -> str:
        messages = [*self.contradictions, *self.reminders]
        return "\n\n".join(f"### {message.kind}\n\n{message.text}" for message in messages)

    def summary(self) -> dict[str, Any]:
        return {
            "schema_version": "cogtrace-grounded-v1",
            "step": self.step_index,
            "event_count": len(self.graph.events),
            "node_count": len(self.graph.nodes),
            "relation_count": len(self.graph.relations),
            "transition_count": sum(len(item.state_transitions) for item in self.results),
            "credit_event_count": len(self.credit_events),
            "guard_count": len(self.contradictions) + len(self.reminders),
        }

    def _add_structured_event_nodes(self, event: NormalizedEvent) -> list[str]:
        if not event.raw_text:
            return []
        kind: str | None = None
        status = "observed"
        metadata: dict[str, Any] = {"related_files": list(event.files)}
        if event.type == "issue":
            if self.graph.find_nodes(kind="goal"):
                return []
            kind, status = "goal", "active"
        elif event.type in {"observation", "test", "diff"}:
            kind = "evidence"
            metadata["verified_source"] = True
            metadata["event_type"] = event.type
            metadata["test_passed"] = event.test_passed
            metadata["test_failed"] = event.test_failed
            metadata["is_environment_error"] = event.is_environment_error
        elif event.type in {"action", "finish"}:
            kind, status = "action", "executed"
        if kind is None:
            return []
        node = GroundedNode(
            kind=kind,  # type: ignore[arg-type]
            canonical_text=event.raw_text[:2000],
            provenance=Provenance.whole_event(event),
            status=status,
            confidence=1.0,
            metadata=metadata,
        )
        before = len(self.graph.nodes)
        node_id = self.graph.add_node(node)
        return [node_id] if len(self.graph.nodes) > before else []

    @staticmethod
    def _normalize(event: NormalizedEvent | TraceStep | Any) -> NormalizedEvent:
        if isinstance(event, NormalizedEvent):
            return event
        if isinstance(event, TraceStep):
            return normalize_trace_step(event)
        raise TypeError("process_event expects NormalizedEvent or TraceStep")
