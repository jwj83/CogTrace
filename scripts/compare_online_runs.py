from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def patch_flags(patch: str) -> dict[str, bool]:
    low = patch.lower()
    return {
        "has_futurewarning": "futurewarning" in low,
        "keeps_ndarraymixin_view": "data.view(ndarraymixin)" in low,
        "mentions_column": "column" in low,
        "uses_required_columns_join": "join" in low and "required_columns" in low,
    }


def summarize_online(output_dir: Path) -> list[dict[str, Any]]:
    rows = read_jsonl(output_dir / "output.jsonl")
    if not rows:
        rows = read_jsonl(output_dir / "output.critic_attempt_1.jsonl")
    summaries = []
    for row in rows:
        test_result = row.get("test_result") or {}
        patch = test_result.get("git_patch") or ""
        instance_id = row.get("instance_id")
        guard_dir = output_dir / "cogtrace_online" / str(instance_id)
        injections = []
        if (guard_dir / "guard_injections.json").exists():
            injections = json.loads(
                (guard_dir / "guard_injections.json").read_text(encoding="utf-8")
            )
        summaries.append(
            {
                "instance_id": instance_id,
                "error": row.get("error"),
                "patch_chars": len(patch),
                "patch_flags": patch_flags(patch),
                "guard_injections": len(injections),
                "metrics": row.get("metrics"),
            }
        )
    return summaries


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare CogTrace online rerun outputs against baseline artifacts."
    )
    parser.add_argument(
        "--online-output-dir", default=str(ROOT / "artifacts" / "online_runs" / "cogtrace")
    )
    parser.add_argument(
        "--baseline-root",
        default=str(ROOT / "artifacts" / "trajectories" / "deepseek_v4_flash_500"),
    )
    args = parser.parse_args()

    online_dir = Path(args.online_output_dir)
    baseline_root = Path(args.baseline_root)
    summaries = summarize_online(online_dir)
    if not summaries:
        print(f"No online output found under {online_dir}")
        return

    print(
        "| Instance | Baseline Patch Chars | Online Patch Chars | "
        "Guard Injections | Online Patch Flags | Error |"
    )
    print("|---|---:|---:|---:|---|---|")
    for item in summaries:
        instance_id = str(item["instance_id"])
        baseline_patch = baseline_root / instance_id / "patch.diff"
        baseline_len = (
            len(baseline_patch.read_text(encoding="utf-8")) if baseline_patch.exists() else 0
        )
        flags = ", ".join(k for k, v in item["patch_flags"].items() if v) or "none"
        error = item["error"] or ""
        print(
            f"| {instance_id} | {baseline_len} | {item['patch_chars']} | "
            f"{item['guard_injections']} | {flags} | {error} |"
        )


if __name__ == "__main__":
    main()
