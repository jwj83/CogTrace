from __future__ import annotations

import pytest

from cog_trace.context import ContextBudget, ContextPacker
from cog_trace.core.graph import CognitiveGraph
from cog_trace.core.schema import GroundedNode, NormalizedEvent, Provenance
from cog_trace.data.split import assert_no_repository_leakage, repository_split


def test_context_profiles_distinguish_model_window_and_state_payload() -> None:
    qwen = ContextBudget.qwen_128k()
    deepseek = ContextBudget.deepseek_512k()
    assert qwen.total_input_tokens == 131_072
    assert qwen.state_tokens == 16_384
    assert deepseek.total_input_tokens == 524_288
    assert deepseek.state_tokens == 32_768
    assert deepseek.payload_tokens < deepseek.total_input_tokens


def test_context_packer_respects_state_and_recent_budgets() -> None:
    graph = CognitiveGraph()
    events = []
    for step in range(10):
        event = NormalizedEvent(
            event_id=f"e{step}", step_id=step, type="thought", raw_text="word " * 10
        )
        graph.add_event(event)
        events.append(event)
        graph.add_node(
            GroundedNode(
                kind="claim",
                canonical_text=f"claim {step} " + "word " * 8,
                provenance=Provenance.whole_event(event),
                status="active",
            )
        )
    budget = ContextBudget(total_input_tokens=100, recent_event_tokens=20, state_tokens=30)
    pack = ContextPacker(budget, token_counter=lambda text: len(text.split())).pack(
        graph, events, 9
    )
    assert pack.estimated_tokens <= budget.payload_tokens


def test_repository_split_has_no_leakage() -> None:
    instances = [f"repo{repo}__task-{task}" for repo in range(10) for task in range(2)]
    splits = repository_split(instances)
    assert_no_repository_leakage(splits)
    assert sum(map(len, splits.values())) == len(instances)

    with pytest.raises(ValueError, match="appears in both"):
        assert_no_repository_leakage({"train": ["django__one"], "test": ["django__two"]})
