from __future__ import annotations

import argparse
import json
from pathlib import Path

from cog_trace.data.split import assert_no_repository_leakage, repository_split


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("trajectories", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", default="cogtrace-v1")
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()
    instance_ids = sorted(
        directory.name
        for directory in args.trajectories.iterdir()
        if directory.is_dir() and (directory / "events.jsonl").exists()
    )
    repositories = {instance.split("__", 1)[0] for instance in instance_ids}
    if args.formal and len(repositories) < 10:
        raise SystemExit(
            f"Formal CogTrace split requires at least 10 repositories; found {len(repositories)}"
        )
    splits = repository_split(instance_ids, seed=args.seed)
    assert_no_repository_leakage(splits)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(splits, indent=2), encoding="utf-8")
    print(json.dumps({key: len(value) for key, value in splits.items()}, indent=2))


if __name__ == "__main__":
    main()
