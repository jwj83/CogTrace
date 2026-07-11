from __future__ import annotations

from cog_trace.core.schema import (
    EvidenceRelation,
    GroundedNode,
    NormalizedEvent,
    Provenance,
)
from cog_trace.extraction.base import ExtractionBatch
from cog_trace.runtime.manager import CogTraceManager


def _node(event: NormalizedEvent, kind: str, text: str, status: str, **metadata):
    return GroundedNode(
        kind=kind,
        canonical_text=text,
        provenance=Provenance.whole_event(event),
        status=status,
        metadata=metadata,
    )


def test_verified_contradiction_refutes_claim() -> None:
    manager = CogTraceManager()
    thought = NormalizedEvent(
        event_id="thought", step_id=1, type="thought", raw_text="Parser strips the suffix"
    )
    evidence = NormalizedEvent(
        event_id="test",
        step_id=2,
        type="test",
        raw_text="Parser preserves the suffix",
        test_passed=True,
    )
    manager.process_event(thought)
    manager.process_event(evidence)
    claim = _node(thought, "claim", thought.raw_text, "candidate", related_files=["parser.py"])
    evidence_node = _node(evidence, "evidence", evidence.raw_text, "observed", verified_source=True)
    claim_id = manager.graph.add_node(claim)
    evidence_id = manager.graph.add_node(evidence_node)
    result = manager.ingest_extraction(
        ExtractionBatch(
            relations=[
                EvidenceRelation(
                    evidence_id=evidence_id,
                    target_id=claim_id,
                    relation="contradicts",
                    verification="verified",
                    verifier_type="deterministic",
                    step_id=2,
                )
            ]
        )
    )
    assert manager.graph.nodes[claim_id].status == "refuted"
    assert result.state_transitions[0].to_status == "refuted"
    assert result.credit_events[0].type == "correct_claim_revision"


def test_environment_error_does_not_refute_claim() -> None:
    manager = CogTraceManager()
    event = NormalizedEvent(
        event_id="env",
        step_id=1,
        type="test",
        raw_text="ModuleNotFoundError",
        test_failed=True,
        is_environment_error=True,
    )
    result = manager.process_event(event)
    assert result.state_transitions == []


def test_unsupported_patch_guard_and_block_limit() -> None:
    class NoopExtractor:
        def extract(self, events):
            return ExtractionBatch(abstained_kinds=["claim"])

    manager = CogTraceManager(extractor=NoopExtractor(), semantic_guards_enabled=True)
    for step in range(1, 4):
        event = NormalizedEvent(
            event_id=f"edit-{step}",
            step_id=step,
            type="action",
            raw_text="write parser.py",
            files=("parser.py",),
            command="write",
            tool_name="file_editor",
        )
        decision = manager.process_event(event).guard_decision
        assert decision is not None
        assert decision.kind == "unsupported_patch"
        assert decision.should_block is (step <= 2)


def test_repeated_read_with_new_information_does_not_false_positive() -> None:
    manager = CogTraceManager()
    for step in range(1, 3):
        result = manager.process_event(
            NormalizedEvent(
                event_id=f"read-{step}",
                step_id=step,
                type="action",
                raw_text="view parser.py",
                files=("parser.py",),
                command="view",
                tool_name="file_editor_view",
            )
        )
        assert result.guard_decision is None
    manager.process_event(
        NormalizedEvent(
            event_id="new-test",
            step_id=3,
            type="test",
            raw_text="new assertion failure",
            test_failed=True,
        )
    )
    result = manager.process_event(
        NormalizedEvent(
            event_id="read-3",
            step_id=4,
            type="action",
            raw_text="view parser.py again",
            files=("parser.py",),
            command="view",
            tool_name="file_editor_view",
        )
    )
    assert result.guard_decision is None
