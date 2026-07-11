from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable

from cog_trace.core.graph import CognitiveGraph
from cog_trace.core.schema import ContextPack, NormalizedEvent

TokenCounter = Callable[[str], int]


def approximate_tokens(text: str) -> int:
    return max(1, (len(text) + 3) // 4) if text else 0


@dataclass(frozen=True)
class ContextBudget:
    """Separate the model window from the CogTrace memory payload."""

    total_input_tokens: int = 131_072
    recent_event_tokens: int = 8_192
    state_tokens: int = 16_384

    @classmethod
    def qwen_128k(cls) -> "ContextBudget":
        return cls(131_072, 8_192, 16_384)

    @classmethod
    def deepseek_512k(cls) -> "ContextBudget":
        return cls(524_288, 16_384, 32_768)

    @classmethod
    def ablation(cls, state_tokens: int, total_input_tokens: int = 131_072) -> "ContextBudget":
        return cls(total_input_tokens, min(8_192, state_tokens), state_tokens)

    @property
    def payload_tokens(self) -> int:
        return self.recent_event_tokens + self.state_tokens

    def validate(self) -> None:
        if min(self.total_input_tokens, self.recent_event_tokens, self.state_tokens) <= 0:
            raise ValueError("context token budgets must be positive")
        if self.payload_tokens >= self.total_input_tokens:
            raise ValueError("CogTrace payload must leave room for system prompts and tools")


def context_budget_from_env() -> ContextBudget:
    profile = os.getenv("COGTRACE_CONTEXT_PROFILE", "qwen-128k").lower()
    base = (
        ContextBudget.deepseek_512k() if profile == "deepseek-512k" else ContextBudget.qwen_128k()
    )
    return ContextBudget(
        total_input_tokens=int(
            os.getenv("COGTRACE_TOTAL_INPUT_TOKENS", str(base.total_input_tokens))
        ),
        recent_event_tokens=int(
            os.getenv("COGTRACE_RECENT_EVENT_TOKENS", str(base.recent_event_tokens))
        ),
        state_tokens=int(os.getenv("COGTRACE_STATE_TOKENS", str(base.state_tokens))),
    )


class ContextPacker:
    def __init__(
        self,
        budget: ContextBudget | None = None,
        token_counter: TokenCounter = approximate_tokens,
    ) -> None:
        self.budget = budget or ContextBudget.qwen_128k()
        self.budget.validate()
        self.token_counter = token_counter

    def pack(
        self,
        graph: CognitiveGraph,
        recent_events: list[NormalizedEvent],
        step_id: int,
    ) -> ContextPack:
        pack = ContextPack(token_budget=self.budget.payload_tokens)
        pack.recent_events = self._take_recent(recent_events)

        state_used = 0

        def add(target: list[dict], node, label: str) -> None:
            nonlocal state_used
            item = {
                "node_id": node.node_id,
                "text": node.canonical_text,
                "status": node.status,
                "confidence": node.confidence,
                "provenance_event_id": node.provenance.event_id,
            }
            cost = self.token_counter(f"{label}: {node.canonical_text} [{node.status}]")
            if state_used + cost <= self.budget.state_tokens:
                target.append(item)
                state_used += cost

        for node in graph.find_nodes(kind="goal"):
            add(pack.goals, node, "Goal")
        for node in graph.find_nodes(kind="constraint", status="unresolved"):
            add(pack.unresolved_constraints, node, "Constraint")
        for node in graph.find_nodes(kind="claim", status="active"):
            add(pack.active_claims, node, "Active claim")
        for node in reversed(graph.find_nodes(kind="claim", status="refuted")):
            add(pack.refuted_claims, node, "Refuted claim")
        evidence = [
            node
            for node in graph.find_nodes(kind="evidence")
            if node.metadata.get("verified_source")
            or any(rel.verification == "verified" for rel in graph.outgoing(node.node_id))
        ]
        for node in reversed(evidence):
            add(pack.verified_evidence, node, "Evidence")
        for node in graph.find_nodes(kind="decision", status="planned"):
            add(pack.pending_decisions, node, "Decision")

        pack.estimated_tokens = state_used + sum(
            self.token_counter(text) for text in pack.recent_events
        )
        return pack

    def _take_recent(self, events: list[NormalizedEvent]) -> list[str]:
        selected: list[str] = []
        used = 0
        for event in reversed(events):
            rendered = f"[{event.step_id}:{event.type}] {event.raw_text}"
            cost = self.token_counter(rendered)
            if used + cost > self.budget.recent_event_tokens:
                continue
            selected.append(rendered)
            used += cost
        return list(reversed(selected))


def render_context_pack(pack: ContextPack) -> str:
    lines = ["<COGTRACE_STATE>"]
    sections = [
        ("GOALS", pack.goals),
        ("UNRESOLVED_CONSTRAINTS", pack.unresolved_constraints),
        ("ACTIVE_CLAIMS", pack.active_claims),
        ("REFUTED_CLAIMS", pack.refuted_claims),
        ("VERIFIED_EVIDENCE", pack.verified_evidence),
        ("PENDING_DECISIONS", pack.pending_decisions),
    ]
    for heading, items in sections:
        if not items:
            continue
        lines.append(heading)
        for item in items:
            lines.append(
                f"- {item['text']} [status={item['status']}; source={item['provenance_event_id']}]"
            )
    if pack.recent_events:
        lines.append("RECENT_EVENTS")
        lines.extend(f"- {item}" for item in pack.recent_events)
    lines.append("</COGTRACE_STATE>")
    return "\n".join(lines)
