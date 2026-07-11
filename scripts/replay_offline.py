"""Replay OpenHands events through the grounded CogTrace pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cog_trace.adapters.openhands_adapter import OpenHandsAdapter
from cog_trace.context import ContextBudget
from cog_trace.runtime.manager import CogTraceManager


def run_offline(
    events_path: Path,
    output_dir: Path,
    *,
    context_profile: str = "qwen-128k",
) -> dict:
    budget = (
        ContextBudget.deepseek_512k()
        if context_profile == "deepseek-512k"
        else ContextBudget.qwen_128k()
    )
    manager = CogTraceManager(context_budget=budget)
    steps = OpenHandsAdapter().iter_steps(events_path)
    result_log: list[dict] = []
    context_packs: list[str] = []

    for step in steps:
        result = manager.process_event(step)
        if result.extraction_requested or result.context_dirty:
            result_log.append(
                {
                    "event_index": step.event_index,
                    **result.to_dict(),
                }
            )
        if result.context_dirty:
            context_packs.append(manager.render())

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        **manager.summary(),
        "total_triggers": sum(item["extraction_requested"] for item in result_log),
        "context_profile": context_profile,
        "context_payload_tokens": budget.payload_tokens,
        "model_input_tokens": budget.total_input_tokens,
    }
    output_dir.joinpath("summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    output_dir.joinpath("events_and_results.jsonl").write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in result_log),
        encoding="utf-8",
    )
    output_dir.joinpath("graph.json").write_text(
        json.dumps(manager.graph.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    output_dir.joinpath("state_snapshots.json").write_text(
        json.dumps(manager.snapshot().to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    output_dir.joinpath("credit_events.json").write_text(
        json.dumps(
            [event.to_dict() for event in manager.credit_events],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output_dir.joinpath("guard_messages.md").write_text(
        manager.render_guard_messages(), encoding="utf-8"
    )
    output_dir.joinpath("context_packs.md").write_text(
        "\n\n---\n\n".join(
            f"### State update {index + 1}\n\n{text}" for index, text in enumerate(context_packs)
        ),
        encoding="utf-8",
    )
    print(f"  wrote {output_dir}")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--trajectories",
        type=Path,
        default=Path("artifacts/trajectories/deepseek_v4_flash_500"),
    )
    parser.add_argument("--output", type=Path, default=Path("artifacts/cogtrace_grounded_v1"))
    parser.add_argument(
        "--context-profile",
        choices=["qwen-128k", "deepseek-512k"],
        default="qwen-128k",
    )
    args = parser.parse_args()

    instance_dirs = sorted(
        directory
        for directory in args.trajectories.iterdir()
        if directory.is_dir() and (directory / "events.jsonl").exists()
    )
    results = []
    for instance_dir in instance_dirs:
        print(f"Processing {instance_dir.name} ...")
        summary = run_offline(
            instance_dir / "events.jsonl",
            args.output / instance_dir.name,
            context_profile=args.context_profile,
        )
        results.append({"instance_id": instance_dir.name, **summary})

    args.output.mkdir(parents=True, exist_ok=True)
    args.output.joinpath("aggregate.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Done. {len(results)} instances processed.")


if __name__ == "__main__":
    main()
