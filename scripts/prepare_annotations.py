from __future__ import annotations

import argparse
import json
from pathlib import Path

from cog_trace.adapters.openhands_adapter import OpenHandsAdapter
from cog_trace.trajectory.normalize import normalize_trace_step


def _is_anchor(event) -> bool:
    if event.type in {"test", "finish", "diff"}:
        return True
    if event.type == "action":
        command = event.command.lower()
        return event.tool_name.lower() == "file_editor" or any(
            marker in command for marker in ("str_replace", "insert", "write", "apply_patch")
        )
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Create grounded annotation-window skeletons.")
    parser.add_argument("trajectories", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--windows", type=int, default=200)
    parser.add_argument("--per-trajectory", type=int, default=5)
    parser.add_argument("--radius", type=int, default=3)
    parser.add_argument("--formal", action="store_true")
    args = parser.parse_args()

    candidates: list[dict] = []
    for directory in sorted(args.trajectories.iterdir()):
        events_file = directory / "events.jsonl"
        if not events_file.exists():
            continue
        events = [normalize_trace_step(step) for step in OpenHandsAdapter().iter_steps(events_file)]
        anchors = [index for index, event in enumerate(events) if _is_anchor(event)]
        for index in anchors[: args.per_trajectory]:
            start = max(0, index - args.radius)
            end = min(len(events), index + args.radius + 1)
            window = events[start:end]
            candidates.append(
                {
                    "trajectory_id": directory.name,
                    "repository": directory.name.split("__", 1)[0],
                    "start_step": window[0].step_id,
                    "end_step": window[-1].step_id,
                    "event_ids": [event.event_id for event in window],
                    "events": [event.to_dict() for event in window],
                    "claims": [],
                    "evidence": [],
                    "action_claim_links": [],
                    "failure_labels": [],
                    "abstained_kinds": [],
                    "annotator_id": "",
                    "metadata": {"anchor_event_id": events[index].event_id},
                }
            )
    selected = candidates[: args.windows]
    repositories = {item["repository"] for item in selected}
    if args.formal:
        if len(selected) != args.windows:
            raise SystemExit(
                f"Formal annotation set requires {args.windows} windows; found {len(selected)}"
            )
        if len(repositories) < 10:
            raise SystemExit(
                "Formal annotation set requires at least 10 repositories; "
                f"found {len(repositories)}"
            )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in selected),
        encoding="utf-8",
    )
    print(f"Wrote {len(selected)} annotation windows to {args.output}")


if __name__ == "__main__":
    main()
