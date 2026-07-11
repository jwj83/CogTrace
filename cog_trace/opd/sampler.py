from __future__ import annotations

from cog_trace.core.schema import CreditEvent

TRAINABLE_FAILURES = {
    "continued_after_refutation",
    "repeated_action_without_information_gain",
    "unsupported_patch",
    "premature_finish",
    "missing_belief_revision",
}


def sample_failure_events(
    events: list[CreditEvent], *, max_per_trajectory: int = 3, minimum_confidence: float = 0.9
) -> list[CreditEvent]:
    candidates = [
        event
        for event in events
        if event.polarity == "negative"
        and event.type in TRAINABLE_FAILURES
        and event.confidence >= minimum_confidence
    ]
    return sorted(candidates, key=lambda item: item.step_id)[:max_per_trajectory]
