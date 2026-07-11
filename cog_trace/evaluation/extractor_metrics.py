from __future__ import annotations

from collections import Counter
from typing import Any


def _prf(true_positive: int, predicted: int, gold: int) -> dict[str, float]:
    precision = true_positive / predicted if predicted else 0.0
    recall = true_positive / gold if gold else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def _span_overlap(first: tuple[int, int], second: tuple[int, int]) -> int:
    return max(0, min(first[1], second[1]) - max(first[0], second[0]))


def evaluate_extractions(
    gold_windows: list[dict[str, Any]], predictions: list[dict[str, Any]]
) -> dict[str, Any]:
    if len(gold_windows) != len(predictions):
        raise ValueError("gold and prediction counts differ")
    correct_claims = predicted_claims = gold_claims = 0
    hallucinations = 0
    exact_spans = 0
    span_scores: list[float] = []
    abstain_tp = abstain_pred = abstain_gold = 0
    transition_counts: Counter[str] = Counter()

    for gold, prediction in zip(gold_windows, predictions, strict=True):
        gold_items = gold.get("claims", [])
        predicted_items = prediction.get("claims", [])
        gold_claims += len(gold_items)
        predicted_claims += len(predicted_items)
        matched_gold: set[int] = set()
        for predicted in predicted_items:
            best_index = None
            for index, expected in enumerate(gold_items):
                if index in matched_gold:
                    continue
                if (
                    predicted.get("text", "").strip().lower()
                    == expected.get("text", "").strip().lower()
                ):
                    best_index = index
                    break
            if best_index is None:
                hallucinations += 1
                continue
            matched_gold.add(best_index)
            correct_claims += 1
            expected = gold_items[best_index]
            predicted_span = predicted.get("provenance", {})
            expected_span = expected.get("provenance", {})
            p = (predicted_span.get("span_start", -1), predicted_span.get("span_end", -1))
            g = (expected_span.get("span_start", -1), expected_span.get("span_end", -1))
            if p == g and predicted_span.get("exact_span") == expected_span.get("exact_span"):
                exact_spans += 1
            overlap = _span_overlap(p, g)
            denom = max(1, (p[1] - p[0]) + (g[1] - g[0]))
            span_scores.append(2 * overlap / denom)
            predicted_transition = (predicted.get("status_before"), predicted.get("status_after"))
            gold_transition = (expected.get("status_before"), expected.get("status_after"))
            transition_counts["gold"] += 1
            transition_counts["predicted"] += 1
            if predicted_transition == gold_transition:
                transition_counts["correct"] += 1

        gold_abstain = bool(gold.get("abstained_kinds")) or not gold_items
        predicted_abstain = bool(prediction.get("abstained_kinds")) or not predicted_items
        abstain_gold += int(gold_abstain)
        abstain_pred += int(predicted_abstain)
        abstain_tp += int(gold_abstain and predicted_abstain)

    return {
        "claim": _prf(correct_claims, predicted_claims, gold_claims),
        "hallucination_rate": hallucinations / predicted_claims if predicted_claims else 0.0,
        "provenance_exact_match": exact_spans / correct_claims if correct_claims else 0.0,
        "provenance_span_f1": sum(span_scores) / len(span_scores) if span_scores else 0.0,
        "abstention": _prf(abstain_tp, abstain_pred, abstain_gold),
        "transition": _prf(
            transition_counts["correct"],
            transition_counts["predicted"],
            transition_counts["gold"],
        ),
        "counts": {
            "gold_claims": gold_claims,
            "predicted_claims": predicted_claims,
            "hallucinations": hallucinations,
        },
    }
