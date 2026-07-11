from __future__ import annotations

from cog_trace.core.schema import (
    EvidenceRelation,
    GroundedNode,
    NormalizedEvent,
    Provenance,
)
from cog_trace.extraction.base import ExtractionBatch
from cog_trace.runtime.manager import CogTraceManager


def test_astropy_13236_refuted_commitment_blocks_related_patch() -> None:
    manager = CogTraceManager(semantic_guards_enabled=True)

    class Extractor:
        def extract(self, events):
            return ExtractionBatch()

    manager.extractor = Extractor()
    thought = NormalizedEvent(
        event_id="commitment",
        step_id=68,
        type="thought",
        raw_text="The structured ndarray auto-transform clause should be removed.",
    )
    evidence = NormalizedEvent(
        event_id="evidence",
        step_id=100,
        type="test",
        raw_text="The warning-only behavior does not remove the transform.",
        test_failed=True,
    )
    manager.process_event(thought)
    manager.process_event(evidence)
    claim = GroundedNode(
        kind="claim",
        canonical_text=thought.raw_text,
        provenance=Provenance.whole_event(thought),
        status="active",
        metadata={"related_files": ["astropy/table/table.py"]},
    )
    ev = GroundedNode(
        kind="evidence",
        canonical_text=evidence.raw_text,
        provenance=Provenance.whole_event(evidence),
        status="observed",
        metadata={"verified_source": True},
    )
    claim_id = manager.graph.add_node(claim)
    evidence_id = manager.graph.add_node(ev)
    manager.ingest_extraction(
        ExtractionBatch(
            relations=[
                EvidenceRelation(
                    evidence_id=evidence_id,
                    target_id=claim_id,
                    relation="contradicts",
                    verification="verified",
                    verifier_type="deterministic",
                    step_id=100,
                )
            ]
        )
    )
    result = manager.process_event(
        NormalizedEvent(
            event_id="patch",
            step_id=122,
            type="action",
            raw_text="write warning-only patch",
            files=("astropy/table/table.py",),
            command="write",
            tool_name="file_editor",
        )
    )
    assert result.guard_decision is not None
    assert result.guard_decision.kind == "continued_after_refutation"


def test_astropy_13033_repeated_read_is_structural_signal() -> None:
    manager = CogTraceManager()
    for step in range(1, 4):
        result = manager.process_event(
            NormalizedEvent(
                event_id=f"read-{step}",
                step_id=step,
                type="action",
                raw_text="view astropy/table/table.py",
                files=("astropy/table/table.py",),
                command="view",
                tool_name="file_editor_view",
            )
        )
    assert result.guard_decision is not None
    assert result.guard_decision.kind == "repeated_exploration"
