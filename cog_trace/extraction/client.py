from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import dataclass

from cog_trace.core.schema import (
    EvidenceRelation,
    GroundedNode,
    NormalizedEvent,
    Provenance,
)
from cog_trace.extraction.base import ExtractionBatch
from cog_trace.extraction.prompt import GROUNDED_EXTRACTION_PROMPT

_DEFAULT_STATUSES = {
    "goal": "active",
    "constraint": "unresolved",
    "claim": "candidate",
    "evidence": "observed",
    "decision": "planned",
    "action": "executed",
}


@dataclass
class OpenAICompatibleGroundedExtractor:
    base_url: str
    model: str
    api_key: str = ""
    timeout_seconds: int = 180

    def extract(self, events: list[NormalizedEvent]) -> ExtractionBatch:
        payload = {
            "model": self.model,
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": GROUNDED_EXTRACTION_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"events": [event.to_dict() for event in events]},
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        request = urllib.request.Request(
            self.base_url.rstrip("/") + "/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                **({"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}),
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            body = json.loads(response.read().decode("utf-8"))
        content = body["choices"][0]["message"]["content"]
        return parse_extraction_response(content, {event.event_id: event for event in events})


def parse_extraction_response(content: str, events: dict[str, NormalizedEvent]) -> ExtractionBatch:
    data = json.loads(content)
    nodes: list[GroundedNode] = []
    node_ids: set[str] = set()
    for item in data.get("nodes", []):
        provenance_data = item["provenance"]
        provenance = Provenance(
            event_id=provenance_data["event_id"],
            exact_span=provenance_data["exact_span"],
            span_start=int(provenance_data["span_start"]),
            span_end=int(provenance_data["span_end"]),
            content_hash=provenance_data["content_hash"],
        )
        event = events.get(provenance.event_id)
        if event is None:
            raise ValueError("extractor referenced an event outside its input batch")
        provenance.validate(event)
        kind = str(item["kind"]).lower()
        node = GroundedNode(
            kind=kind,  # type: ignore[arg-type]
            canonical_text=str(item["canonical_text"]),
            provenance=provenance,
            status=str(item.get("status") or _DEFAULT_STATUSES[kind]),
            confidence=float(item.get("confidence", 1.0)),
            node_id=str(item.get("node_id", "")),
            metadata=dict(item.get("metadata", {})),
        )
        if not node.node_id:
            raise ValueError("extractor nodes require stable node_id values")
        if node.node_id in node_ids:
            raise ValueError("extractor returned duplicate node_id values")
        node_ids.add(node.node_id)
        nodes.append(node)

    relations = []
    for item in data.get("relations", []):
        if item["evidence_id"] not in node_ids or item["target_id"] not in node_ids:
            raise ValueError("extraction relation must reference nodes in the same batch")
        relations.append(
            EvidenceRelation(
                evidence_id=item["evidence_id"],
                target_id=item["target_id"],
                relation=item["relation"],
                verification="proposed",
                verifier_type="semantic",
                step_id=max(events[event_id].step_id for event_id in events),
                metadata={
                    **dict(item.get("metadata", {})),
                    "model_proposed_verification": item.get("verification", "proposed"),
                },
            )
        )
    return ExtractionBatch(
        nodes=nodes,
        relations=relations,
        abstained_kinds=list(data.get("abstained_kinds", [])),
        raw_response=content,
    )


def extractor_from_env() -> OpenAICompatibleGroundedExtractor | None:
    base_url = os.getenv("COGTRACE_EXTRACTOR_BASE_URL", "").strip()
    model = os.getenv("COGTRACE_EXTRACTOR_MODEL", "").strip()
    if not base_url or not model:
        return None
    return OpenAICompatibleGroundedExtractor(
        base_url=base_url,
        model=model,
        api_key=os.getenv("COGTRACE_EXTRACTOR_API_KEY", ""),
        timeout_seconds=int(os.getenv("COGTRACE_EXTRACTOR_TIMEOUT", "180")),
    )
