from __future__ import annotations

import random
from collections import defaultdict
from typing import Iterable


def binary_metrics(
    labels: list[int], scores: list[float], threshold: float = 0.5
) -> dict[str, float]:
    if len(labels) != len(scores):
        raise ValueError("labels and scores must have the same length")
    predicted = [int(score >= threshold) for score in scores]
    true_positive = sum(
        label == 1 and guess == 1 for label, guess in zip(labels, predicted, strict=True)
    )
    false_positive = sum(
        label == 0 and guess == 1 for label, guess in zip(labels, predicted, strict=True)
    )
    false_negative = sum(
        label == 1 and guess == 0 for label, guess in zip(labels, predicted, strict=True)
    )
    precision = (
        true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    )
    recall = (
        true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    )
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "auprc": average_precision(labels, scores),
    }


def average_precision(labels: list[int], scores: list[float]) -> float:
    positives = sum(labels)
    if not positives:
        return 0.0
    ordered = sorted(zip(scores, labels, strict=True), reverse=True)
    true_positive = 0
    total = 0
    precision_sum = 0.0
    for _, label in ordered:
        total += 1
        if label:
            true_positive += 1
            precision_sum += true_positive / total
    return precision_sum / positives


def clustered_bootstrap_difference(
    rows: Iterable[tuple[str, int, float, float]],
    *,
    iterations: int = 2000,
    seed: int = 7,
) -> dict[str, float]:
    """Bootstrap AUPRC(A)-AUPRC(B) while resampling whole trajectories."""
    clusters: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
    for trajectory_id, label, first, second in rows:
        clusters[trajectory_id].append((label, first, second))
    cluster_ids = sorted(clusters)
    if not cluster_ids:
        raise ValueError("at least one cluster is required")
    rng = random.Random(seed)
    differences = []
    for _ in range(iterations):
        sampled = [rng.choice(cluster_ids) for _ in cluster_ids]
        labels: list[int] = []
        first_scores: list[float] = []
        second_scores: list[float] = []
        for cluster_id in sampled:
            for label, first, second in clusters[cluster_id]:
                labels.append(label)
                first_scores.append(first)
                second_scores.append(second)
        differences.append(
            average_precision(labels, first_scores) - average_precision(labels, second_scores)
        )
    differences.sort()
    low = differences[int(0.025 * (iterations - 1))]
    high = differences[int(0.975 * (iterations - 1))]
    return {
        "mean_difference": sum(differences) / len(differences),
        "ci95_low": low,
        "ci95_high": high,
    }
