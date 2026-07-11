from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Iterable


def repository_from_instance(instance_id: str) -> str:
    return instance_id.split("__", 1)[0]


def repository_split(
    instance_ids: Iterable[str],
    *,
    seed: str = "cogtrace-v1",
) -> dict[str, list[str]]:
    """Deterministic 60/20/20 split with repository-level isolation."""
    by_repo: dict[str, list[str]] = defaultdict(list)
    for instance_id in instance_ids:
        by_repo[repository_from_instance(instance_id)].append(instance_id)
    repositories = sorted(
        by_repo,
        key=lambda repo: hashlib.sha256(f"{seed}:{repo}".encode()).hexdigest(),
    )
    count = len(repositories)
    train_end = max(1, round(count * 0.60)) if count else 0
    dev_end = max(train_end + 1, round(count * 0.80)) if count > 1 else train_end
    assignments = {
        "train": repositories[:train_end],
        "dev": repositories[train_end:dev_end],
        "test": repositories[dev_end:],
    }
    return {
        split: sorted(instance for repo in repos for instance in by_repo[repo])
        for split, repos in assignments.items()
    }


def assert_no_repository_leakage(splits: dict[str, list[str]]) -> None:
    seen: dict[str, str] = {}
    for split, instances in splits.items():
        for instance in instances:
            repository = repository_from_instance(instance)
            previous = seen.setdefault(repository, split)
            if previous != split:
                raise ValueError(
                    f"repository {repository!r} appears in both {previous} and {split}"
                )
