from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field

from cog_trace.core.graph import CognitiveGraph
from cog_trace.core.schema import GuardDecision, NormalizedEvent


@dataclass
class GuardPolicy:
    max_consecutive_blocks: int = 2
    repeat_window_actions: int = 20
    repeat_threshold: int = 3
    _action_index: int = 0
    _information_version: int = 0
    _file_reads: dict[str, deque[tuple[int, int]]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    _block_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _edit_count: int = 0
    _last_functional_test_passed: bool | None = None

    def note_information_change(self) -> None:
        self._information_version += 1

    def evaluate(
        self,
        event: NormalizedEvent,
        graph: CognitiveGraph,
        *,
        semantic_state_available: bool = True,
    ) -> GuardDecision | None:
        if event.type == "action":
            self._action_index += 1
        decision = (
            self._continued_after_refutation(event, graph) if semantic_state_available else None
        )
        if decision is None and semantic_state_available:
            decision = self._unsupported_patch(event, graph)
        if decision is None:
            decision = self._repeated_exploration(event)
        if decision is None:
            decision = self._premature_finish(event, graph)
        if decision is not None:
            count = self._block_counts[decision.kind]
            decision.should_block = count < self.max_consecutive_blocks
            self._block_counts[decision.kind] = count + 1
        return decision

    def observe(self, event: NormalizedEvent) -> None:
        if self._is_edit(event):
            self._edit_count += 1
        if event.type == "test" and not event.is_environment_error:
            if event.test_passed:
                self._last_functional_test_passed = True
            elif event.test_failed:
                self._last_functional_test_passed = False
        if self._is_read(event):
            for path in event.files:
                reads = self._file_reads[path]
                reads.append((self._action_index, self._information_version))
                while reads and self._action_index - reads[0][0] > self.repeat_window_actions:
                    reads.popleft()

    def _continued_after_refutation(
        self, event: NormalizedEvent, graph: CognitiveGraph
    ) -> GuardDecision | None:
        if not self._is_edit(event) or not event.files:
            return None
        related = []
        event_files = set(event.files)
        for claim in graph.find_nodes(kind="claim", status="refuted"):
            claim_files = set(claim.metadata.get("related_files", []))
            if claim_files and claim_files & event_files:
                related.append(claim)
        if not related:
            return None
        evidence = []
        for claim in related:
            for relation in graph.incoming(claim.node_id, "contradicts"):
                if relation.verification == "verified":
                    node = graph.nodes.get(relation.evidence_id)
                    if node:
                        evidence.append(node.canonical_text)
        return GuardDecision(
            kind="continued_after_refutation",
            should_block=True,
            step_id=event.step_id,
            severity="error",
            related_node_ids=[claim.node_id for claim in related],
            message=(
                "This edit targets files associated with a refuted claim. "
                f"Contradicting evidence: {'; '.join(evidence[:2]) or 'see CogTrace state'}. "
                "Revise the claim or provide new verified evidence before editing."
            ),
        )

    def _unsupported_patch(
        self, event: NormalizedEvent, graph: CognitiveGraph
    ) -> GuardDecision | None:
        if not self._is_edit(event):
            return None
        active = graph.find_nodes(kind="claim", status="active")
        if active:
            return None
        return GuardDecision(
            kind="unsupported_patch",
            should_block=True,
            step_id=event.step_id,
            severity="warning",
            message=(
                "No active grounded claim justifies this patch. State the claim being "
                "tested and cite repository or test evidence before editing."
            ),
        )

    def _repeated_exploration(self, event: NormalizedEvent) -> GuardDecision | None:
        if not self._is_read(event):
            return None
        for path in event.files:
            reads = self._file_reads[path]
            same_information_reads = [
                item for item in reads if item[1] == self._information_version
            ]
            if len(same_information_reads) >= self.repeat_threshold - 1:
                return GuardDecision(
                    kind="repeated_exploration",
                    should_block=True,
                    step_id=event.step_id,
                    severity="warning",
                    message=(
                        f"'{path}' has already been inspected repeatedly without new "
                        "evidence or a revised information need. Explain what new question "
                        "this read will answer."
                    ),
                )
        return None

    def _premature_finish(
        self, event: NormalizedEvent, graph: CognitiveGraph
    ) -> GuardDecision | None:
        if event.type != "finish":
            return None
        unresolved = graph.find_nodes(kind="constraint", status="unresolved")
        reasons = [node.canonical_text for node in unresolved[:3]]
        if self._last_functional_test_passed is False:
            reasons.append("the latest functional test failed")
        elif self._edit_count and self._last_functional_test_passed is None:
            reasons.append("code was edited without a successful functional test")
        if not reasons:
            return None
        return GuardDecision(
            kind="premature_finish",
            should_block=True,
            step_id=event.step_id,
            severity="error",
            related_node_ids=[node.node_id for node in unresolved],
            message="Cannot finish yet: " + "; ".join(reasons) + ". Provide verification evidence.",
        )

    @staticmethod
    def _is_edit(event: NormalizedEvent) -> bool:
        command = event.command.lower()
        return event.type == "action" and (
            event.tool_name.lower() == "file_editor"
            or any(
                marker in command
                for marker in ("str_replace", "insert", "create", "write", "apply_patch")
            )
        )

    @classmethod
    def _is_read(cls, event: NormalizedEvent) -> bool:
        return event.type == "action" and bool(event.files) and not cls._is_edit(event)
