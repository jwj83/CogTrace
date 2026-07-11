from __future__ import annotations

import pytest

from cog_trace.core.graph import CognitiveGraph
from cog_trace.core.schema import GroundedNode, NormalizedEvent, Provenance


def test_provenance_requires_exact_span_and_hash() -> None:
    event = NormalizedEvent(
        event_id="e1", step_id=1, type="thought", raw_text="The parser may be wrong."
    )
    graph = CognitiveGraph()
    graph.add_event(event)
    start = event.raw_text.index("parser")
    valid = Provenance(
        event_id="e1",
        exact_span="parser",
        span_start=start,
        span_end=start + len("parser"),
        content_hash=event.content_hash,
    )
    node = GroundedNode(
        kind="claim",
        canonical_text="The parser may be wrong",
        provenance=valid,
        status="candidate",
    )
    assert graph.add_node(node).startswith("claim_")

    invalid = Provenance(
        event_id="e1",
        exact_span="normalizer",
        span_start=start,
        span_end=start + len("parser"),
        content_hash=event.content_hash,
    )
    with pytest.raises(ValueError, match="exact_span"):
        graph.add_node(
            GroundedNode(
                kind="claim",
                canonical_text="A fabricated claim",
                provenance=invalid,
                status="candidate",
            )
        )


def test_duplicate_event_is_idempotent_but_collision_is_rejected() -> None:
    graph = CognitiveGraph()
    event = NormalizedEvent(event_id="same", step_id=1, type="action", raw_text="read a.py")
    assert graph.add_event(event)
    assert not graph.add_event(event)
    with pytest.raises(ValueError, match="collision"):
        graph.add_event(
            NormalizedEvent(event_id="same", step_id=2, type="action", raw_text="edit b.py")
        )
