from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from cog_trace.adapters.openhands_adapter import OpenHandsAdapter

ROOT = Path(__file__).resolve().parents[1]


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def clip(text: str, limit: int = 360) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


def node_index(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {node["id"]: node for node in graph.get("nodes", [])}


def format_node(node: dict[str, Any]) -> str:
    status = node.get("status", "")
    confidence = node.get("confidence")
    confidence_text = f", conf={confidence:.2f}" if isinstance(confidence, (int, float)) else ""
    return (
        f"- step {node['source_event']} | {node['type']} ({status}{confidence_text}): "
        f"{clip(node['text'])}"
    )


def format_event_snippet(events_by_index: dict[int, Any], event_index: int) -> str:
    step = events_by_index.get(event_index)
    if not step:
        return ""
    text = step.thought or step.observation or step.message or step.text
    text = clip(text, 500)
    if not text:
        return ""
    return f"\n  Evidence snippet: {text}"


def render_report(instance_id: str, output_dir: Path, events_path: Path) -> str:
    graph = load_json(output_dir / "graph.json")
    summary = load_json(output_dir / "summary.json")
    contradictions = load_json(output_dir / "contradictions.json")
    reminders = load_json(output_dir / "reminders.json")
    trigger_log = load_json(output_dir / "trigger_log.json")
    nodes = node_index(graph)
    steps = OpenHandsAdapter().iter_steps(events_path)
    events_by_index = {step.event_index: step for step in steps}

    important_types = {"Goal", "Constraint", "Hypothesis", "Decision", "Patch", "TestResult"}
    timeline = [
        node
        for node in graph.get("nodes", [])
        if node.get("type") in important_types and not node.get("metadata", {}).get("generic")
    ]
    timeline = sorted(timeline, key=lambda node: (node["source_event"], node["type"]))[:20]

    lines: list[str] = [
        f"# CogTrace Case Report: {instance_id}",
        "",
        "## Run Summary",
        "",
        f"- Events: {summary['event_count']}",
        f"- Extracted cognitive nodes: {summary['node_count']}",
        f"- Graph edges: {summary['edge_count']}",
        f"- Triggered checkpoints: {summary['trigger_count']}",
        f"- Contradictions: {summary['contradiction_count']}",
        f"- Reminders: {summary['reminder_count']}",
        "",
        "## Cognitive Timeline",
        "",
    ]
    lines.extend(format_node(node) for node in timeline)

    lines.extend(["", "## Contradictions", ""])
    if contradictions:
        for item in contradictions:
            source = nodes.get(item["source_node"], {})
            target = nodes.get(item["target_node"], {})
            lines.extend(
                [
                    f"### {item['id']}",
                    "",
                    f"- Severity: {item['severity']}",
                    f"- Earlier {target.get('type', 'node')} at step "
                    f"{target.get('source_event')}: {clip(target.get('text', ''))}",
                    f"- Later {source.get('type', 'node')} at step "
                    f"{source.get('source_event')}: {clip(source.get('text', ''))}",
                    f"- Detector reason: {item['description']}",
                    format_event_snippet(
                        events_by_index, int(source.get("source_event", item["source_event"]))
                    ),
                    "",
                ]
            )
    else:
        lines.append("No semantic contradiction detected.")

    lines.extend(["", "## Context Reminders", ""])
    if reminders:
        for item in reminders:
            node = nodes.get(item["node_id"], {})
            lines.extend(
                [
                    f"- step {item['source_event']} | {item['type']}: {item['description']}",
                    f"  Active commitment: {clip(node.get('text', ''))}",
                ]
            )
    else:
        lines.append("No reminder generated.")

    lines.extend(["", "## Trigger Policy Audit", ""])
    trigger_counts: dict[str, int] = {}
    for record in trigger_log:
        trigger_counts[record["trigger"]] = trigger_counts.get(record["trigger"], 0) + 1
    for trigger, count in sorted(trigger_counts.items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- {trigger}: {count}")

    lines.extend(["", "## Paper Takeaway", ""])
    if contradictions:
        lines.append(
            "This trajectory supports the cognitive-contradiction story: the agent "
            "formed an explicit commitment, later produced a patch that violated it, "
            "and CogTrace catches the conflict at "
            "the patch checkpoint instead of only at final submission."
        )
    elif reminders:
        lines.append(
            "This trajectory supports the cognitive-context story: no direct "
            "contradiction was found, but CogTrace detected repeated exploration while "
            "an earlier high-confidence commitment remained unresolved, which is exactly "
            "the context-selection failure mode we want to reduce."
        )
    else:
        lines.append(
            "This trajectory did not trigger a contradiction or reminder under the "
            "current conservative rules."
        )
    lines.append("")
    return "\n".join(lines)


def find_instances(output_root: Path, instance: str | None) -> list[Path]:
    if instance:
        output_dir = output_root / instance
        if not output_dir.exists():
            raise FileNotFoundError(output_dir)
        return [output_dir]
    return sorted(
        path for path in output_root.iterdir() if path.is_dir() and (path / "summary.json").exists()
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Render human-readable CogTrace case reports.")
    parser.add_argument("--output-root", default=str(ROOT / "artifacts" / "cogtrace"))
    parser.add_argument(
        "--trajectory-root",
        default=str(ROOT / "artifacts" / "trajectories" / "deepseek_v4_flash_500"),
    )
    parser.add_argument("--instance", default=None)
    args = parser.parse_args()

    output_root = Path(args.output_root)
    trajectory_root = Path(args.trajectory_root)
    for output_dir in find_instances(output_root, args.instance):
        instance_id = output_dir.name
        events_path = trajectory_root / instance_id / "events.jsonl"
        if not events_path.exists():
            raise FileNotFoundError(events_path)
        report = render_report(instance_id, output_dir, events_path)
        report_path = output_dir / "case_report.md"
        report_path.write_text(report, encoding="utf-8")
        print(report_path)


if __name__ == "__main__":
    main()
