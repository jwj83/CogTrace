from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from typing import Any

from cog_trace.core.schema import (
    EvidenceRelation,
    GroundedNode,
    NormalizedEvent,
    StateSnapshot,
)


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower()).replace("`", "")


class CognitiveGraph:
    """In-memory grounded state graph with deterministic JSON export."""

    def __init__(self) -> None:
        self.events: dict[str, NormalizedEvent] = {}
        self.nodes: dict[str, GroundedNode] = {}
        self.relations: list[EvidenceRelation] = []
        self._node_index: dict[tuple[str, str], str] = {}
        self._outgoing: dict[str, list[EvidenceRelation]] = defaultdict(list)
        self._incoming: dict[str, list[EvidenceRelation]] = defaultdict(list)

    @property
    def edges(self) -> list[EvidenceRelation]:
        return self.relations

    def add_event(self, event: NormalizedEvent) -> bool:
        current = self.events.get(event.event_id)
        if current:
            if current.content_hash != event.content_hash:
                raise ValueError(f"event_id collision with different content: {event.event_id}")
            return False
        self.events[event.event_id] = event
        return True

    def add_node(self, node: GroundedNode) -> str:
        event = self.events.get(node.provenance.event_id)
        if event is None:
            raise ValueError(f"unknown provenance event: {node.provenance.event_id}")
        node.provenance.validate(event)
        if not node.canonical_text.strip():
            raise ValueError("node canonical_text must not be empty")

        key = (node.kind, normalize_text(node.canonical_text))
        existing_id = self._node_index.get(key)
        if existing_id:
            current = self.nodes[existing_id]
            current.updated_step = max(current.updated_step, event.step_id)
            current.confidence = max(current.confidence, node.confidence)
            current.metadata.update(
                {key: value for key, value in node.metadata.items() if value not in (None, "", [])}
            )
            return existing_id

        digest = hashlib.sha1(
            f"{node.kind}:{normalize_text(node.canonical_text)}".encode("utf-8")
        ).hexdigest()[:12]
        node.node_id = node.node_id or f"{node.kind}_{digest}"
        node.created_step = event.step_id
        node.updated_step = event.step_id
        self.nodes[node.node_id] = node
        self._node_index[key] = node.node_id
        return node.node_id

    def add_relation(self, relation: EvidenceRelation) -> str:
        evidence = self.nodes.get(relation.evidence_id)
        target = self.nodes.get(relation.target_id)
        if evidence is None or target is None:
            raise ValueError("relation endpoints must already exist")
        if evidence.kind != "evidence":
            raise ValueError("relation source must be an evidence node")
        for current in self.relations:
            if (
                current.evidence_id == relation.evidence_id
                and current.target_id == relation.target_id
                and current.relation == relation.relation
            ):
                if current.verification == "proposed" and relation.verification != "proposed":
                    current.verification = relation.verification
                    current.verifier_type = relation.verifier_type
                current.metadata.update(relation.metadata)
                return current.relation_id

        digest = hashlib.sha1(
            f"{relation.evidence_id}:{relation.relation}:{relation.target_id}".encode("utf-8")
        ).hexdigest()[:12]
        relation.relation_id = relation.relation_id or f"relation_{digest}"
        self.relations.append(relation)
        self._outgoing[relation.evidence_id].append(relation)
        self._incoming[relation.target_id].append(relation)
        return relation.relation_id

    def add_edge(
        self,
        source: str,
        target: str,
        edge_type: str,
        source_event: int,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.add_relation(
            EvidenceRelation(
                evidence_id=source,
                target_id=target,
                relation=edge_type,  # type: ignore[arg-type]
                verification="proposed",
                verifier_type="semantic",
                step_id=source_event,
                metadata=metadata or {},
            )
        )

    def set_status(self, node_id: str, status: str, step_id: int) -> None:
        node = self.nodes[node_id]
        node.status = status
        node.updated_step = step_id

    def find_nodes(
        self,
        node_type: str | None = None,
        status: str | None = None,
        contains: str | None = None,
        *,
        kind: str | None = None,
    ) -> list[GroundedNode]:
        requested_kind = kind
        if requested_kind is None and node_type:
            requested_kind = {
                "Hypothesis": "claim",
                "Claim": "claim",
            }.get(node_type, node_type.lower())
        needle = normalize_text(contains) if contains else ""
        result = []
        for node in self.nodes.values():
            if requested_kind and node.kind != requested_kind:
                continue
            if status and node.status != status:
                continue
            if needle and needle not in normalize_text(node.canonical_text):
                continue
            result.append(node)
        return sorted(result, key=lambda item: (item.created_step, item.kind, item.canonical_text))

    def outgoing(self, node_id: str, edge_type: str | None = None) -> list[EvidenceRelation]:
        return [
            item
            for item in self._outgoing.get(node_id, [])
            if edge_type is None or item.relation == edge_type
        ]

    def incoming(self, node_id: str, edge_type: str | None = None) -> list[EvidenceRelation]:
        return [
            item
            for item in self._incoming.get(node_id, [])
            if edge_type is None or item.relation == edge_type
        ]

    def snapshot(self, step_id: int) -> StateSnapshot:
        def rows(nodes: list[GroundedNode]) -> list[dict[str, Any]]:
            return [
                {
                    "node_id": node.node_id,
                    "text": node.canonical_text,
                    "status": node.status,
                    "confidence": node.confidence,
                    "metadata": node.metadata,
                }
                for node in nodes
            ]

        verified_evidence = []
        for node in self.find_nodes(kind="evidence"):
            if any(
                relation.verification == "verified" for relation in self.outgoing(node.node_id)
            ) or node.metadata.get("verified_source"):
                verified_evidence.append(node)
        return StateSnapshot(
            step_id=step_id,
            active_claims=rows(self.find_nodes(kind="claim", status="active")),
            refuted_claims=rows(self.find_nodes(kind="claim", status="refuted")),
            unresolved_constraints=rows(self.find_nodes(kind="constraint", status="unresolved")),
            verified_evidence=rows(verified_evidence),
            pending_decisions=rows(self.find_nodes(kind="decision", status="planned")),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "cogtrace-grounded-v1",
            "events": [
                event.to_dict()
                for event in sorted(self.events.values(), key=lambda item: item.step_id)
            ],
            "nodes": [
                node.to_dict()
                for node in sorted(
                    self.nodes.values(),
                    key=lambda item: (item.created_step, item.kind, item.canonical_text),
                )
            ],
            "relations": [relation.to_dict() for relation in self.relations],
            "edges": [relation.to_dict() for relation in self.relations],
        }
