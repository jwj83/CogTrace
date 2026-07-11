from __future__ import annotations

from collections import Counter


def cohens_kappa(first: list[str], second: list[str]) -> float:
    if len(first) != len(second) or not first:
        raise ValueError("two non-empty equally sized label lists are required")
    observed = sum(a == b for a, b in zip(first, second, strict=True)) / len(first)
    first_counts = Counter(first)
    second_counts = Counter(second)
    labels = set(first_counts) | set(second_counts)
    expected = sum(
        first_counts[label] / len(first) * second_counts[label] / len(second) for label in labels
    )
    return (observed - expected) / (1 - expected) if expected < 1 else 1.0


def span_f1(first: tuple[int, int], second: tuple[int, int]) -> float:
    overlap = max(0, min(first[1], second[1]) - max(first[0], second[0]))
    denominator = (first[1] - first[0]) + (second[1] - second[0])
    return 2 * overlap / denominator if denominator > 0 else 1.0
