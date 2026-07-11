from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from cog_trace.core.schema import EvidenceRelation, GroundedNode, NormalizedEvent


@dataclass
class ExtractionBatch:
    nodes: list[GroundedNode] = field(default_factory=list)
    relations: list[EvidenceRelation] = field(default_factory=list)
    abstained_kinds: list[str] = field(default_factory=list)
    raw_response: str = ""


class GroundedExtractor(Protocol):
    def extract(self, events: list[NormalizedEvent]) -> ExtractionBatch:
        """Return candidates whose provenance points only into ``events``."""
        ...
