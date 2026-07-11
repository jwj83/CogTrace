from __future__ import annotations

import json

import pytest

from cog_trace.core.schema import NormalizedEvent
from cog_trace.extraction.client import parse_extraction_response


def test_client_validates_exact_grounding_and_demotes_semantic_verification() -> None:
    event = NormalizedEvent(
        event_id="e1", step_id=1, type="thought", raw_text="The parser may be wrong"
    )
    start = event.raw_text.index("parser")
    response = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "c1",
                    "kind": "claim",
                    "canonical_text": "The parser may be wrong",
                    "status": "candidate",
                    "provenance": {
                        "event_id": "e1",
                        "exact_span": "parser",
                        "span_start": start,
                        "span_end": start + len("parser"),
                        "content_hash": event.content_hash,
                    },
                },
                {
                    "node_id": "ev1",
                    "kind": "evidence",
                    "canonical_text": "Agent statement",
                    "provenance": {
                        "event_id": "e1",
                        "exact_span": event.raw_text,
                        "span_start": 0,
                        "span_end": len(event.raw_text),
                        "content_hash": event.content_hash,
                    },
                },
            ],
            "relations": [
                {
                    "evidence_id": "ev1",
                    "target_id": "c1",
                    "relation": "supports",
                    "verification": "verified",
                }
            ],
        }
    )
    batch = parse_extraction_response(response, {event.event_id: event})
    assert batch.relations[0].verification == "proposed"
    assert batch.relations[0].metadata["model_proposed_verification"] == "verified"


def test_client_rejects_out_of_batch_event() -> None:
    event = NormalizedEvent(event_id="e1", step_id=1, type="thought", raw_text="text")
    response = json.dumps(
        {
            "nodes": [
                {
                    "node_id": "c1",
                    "kind": "claim",
                    "canonical_text": "claim",
                    "provenance": {
                        "event_id": "not-present",
                        "exact_span": "text",
                        "span_start": 0,
                        "span_end": 4,
                        "content_hash": event.content_hash,
                    },
                }
            ]
        }
    )
    with pytest.raises(ValueError, match="outside"):
        parse_extraction_response(response, {event.event_id: event})


def test_missing_extractor_fails_open_for_semantic_guards() -> None:
    from cog_trace.runtime.manager import CogTraceManager

    manager = CogTraceManager()
    result = manager.process_event(
        NormalizedEvent(
            event_id="edit",
            step_id=1,
            type="action",
            raw_text="write parser.py",
            files=("parser.py",),
            command="write",
            tool_name="file_editor",
        )
    )
    assert result.guard_decision is None
