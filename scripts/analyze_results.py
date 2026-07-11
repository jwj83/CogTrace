from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize CogTrace offline outputs.")
    parser.add_argument("--output-root", default="artifacts/cogtrace")
    args = parser.parse_args()

    root = Path(args.output_root)
    rows = []
    for summary_path in sorted(root.glob("*/summary.json")):
        data = json.loads(summary_path.read_text(encoding="utf-8"))
        data["instance_id"] = summary_path.parent.name
        rows.append(data)

    print("| Instance | Nodes | Edges | Triggers | Contradictions | Reminders |")
    print("|---|---:|---:|---:|---:|---:|")
    for row in rows:
        print(
            f"| {row['instance_id']} | {row['node_count']} | {row['edge_count']} | "
            f"{row['trigger_count']} | {row['contradiction_count']} | {row['reminder_count']} |"
        )


if __name__ == "__main__":
    main()
