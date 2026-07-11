from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARKS = ROOT / "benchmarks"
DEFAULT_INSTANCES = ["astropy__astropy-13236", "astropy__astropy-13033"]


def write_selection(path: Path, instances: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(instances) + "\n", encoding="utf-8")


def validate_prereqs(llm_config: Path, workspace: str) -> list[str]:
    problems: list[str] = []
    if not llm_config.exists():
        problems.append(f"LLM config not found: {llm_config}")
    else:
        try:
            cfg = json.loads(llm_config.read_text(encoding="utf-8"))
            api_key = str(cfg.get("api_key", ""))
            if not api_key or "YOUR_API_KEY" in api_key:
                problems.append(f"LLM config has no real api_key: {llm_config}")
        except Exception as exc:
            problems.append(f"Could not parse LLM config {llm_config}: {exc}")
    if not (BENCHMARKS / "vendor" / "software-agent-sdk" / "openhands-sdk").exists():
        problems.append(
            "OpenHands SDK submodule is missing; run "
            "`git submodule update --init --recursive` in benchmarks."
        )
    if workspace == "remote" and not os.getenv("RUNTIME_API_KEY"):
        problems.append("RUNTIME_API_KEY is not set for remote workspace.")
    if workspace == "docker":
        try:
            subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=20,
            )
        except Exception as exc:
            problems.append(f"Docker daemon is not ready for docker workspace: {exc}")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run OpenHands SWE-bench with CogTrace online guard enabled."
    )
    parser.add_argument("llm_config", help="Path to OpenHands LLM config JSON.")
    parser.add_argument("--instances", nargs="*", default=DEFAULT_INSTANCES)
    parser.add_argument("--workspace", choices=["docker", "remote", "apptainer"], default="docker")
    parser.add_argument(
        "--output-dir", default=str(ROOT / "artifacts" / "online_runs" / "cogtrace")
    )
    parser.add_argument("--max-iterations", type=int, default=500)
    parser.add_argument("--num-workers", type=int, default=1)
    parser.add_argument("--condenser-max-size", type=int)
    parser.add_argument("--condenser-max-tokens", type=int)
    parser.add_argument("--condenser-max-output-tokens", type=int)
    parser.add_argument("--condenser-keep-first", type=int)
    parser.add_argument(
        "--context-profile",
        choices=["qwen-128k", "deepseek-512k"],
        default="qwen-128k",
    )
    parser.add_argument("--cogtrace-state-tokens", type=int)
    parser.add_argument("--cogtrace-recent-tokens", type=int)
    parser.add_argument(
        "--mode",
        choices=["shadow", "intervene"],
        default="intervene",
        help="Shadow records state only; intervene enables CogTrace context and guards.",
    )
    parser.add_argument("--no-cogtrace", action="store_true")
    parser.add_argument("--dataset", default="princeton-nlp/SWE-bench_Verified")
    parser.add_argument("--split", default="test")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    llm_config = Path(args.llm_config)
    if not llm_config.is_absolute():
        llm_config = (Path.cwd() / llm_config).resolve()

    problems = validate_prereqs(llm_config, args.workspace)
    if problems:
        print("Cannot start online rerun:")
        for problem in problems:
            print(f"- {problem}")
        sys.exit(2)

    output_dir = Path(args.output_dir).resolve()
    selection_path = output_dir / "selected_instances.txt"
    write_selection(selection_path, args.instances)

    cmd = [
        "uv",
        "run",
        "--with-editable",
        str(ROOT),
        "swebench-infer",
        str(llm_config),
        "--dataset",
        args.dataset,
        "--split",
        args.split,
        "--workspace",
        args.workspace,
        "--select",
        str(selection_path),
        "--output-dir",
        str(output_dir),
        "--max-iterations",
        str(args.max_iterations),
        "--num-workers",
        str(args.num_workers),
        "--n-critic-runs",
        "1",
    ]
    if args.condenser_max_size is not None:
        cmd.extend(["--condenser-max-size", str(args.condenser_max_size)])
    if args.condenser_max_tokens is not None:
        cmd.extend(["--condenser-max-tokens", str(args.condenser_max_tokens)])
    if args.condenser_max_output_tokens is not None:
        cmd.extend(["--condenser-max-output-tokens", str(args.condenser_max_output_tokens)])
    if args.condenser_keep_first is not None:
        cmd.extend(["--condenser-keep-first", str(args.condenser_keep_first)])

    env = os.environ.copy()
    if args.no_cogtrace:
        env.pop("COGTRACE_ONLINE", None)
    else:
        env["COGTRACE_ONLINE"] = "1"
        env["COGTRACE_MODE"] = args.mode
        env["COGTRACE_CONTEXT_PROFILE"] = args.context_profile
        if args.cogtrace_state_tokens is not None:
            env["COGTRACE_STATE_TOKENS"] = str(args.cogtrace_state_tokens)
        if args.cogtrace_recent_tokens is not None:
            env["COGTRACE_RECENT_EVENT_TOKENS"] = str(args.cogtrace_recent_tokens)
    env.setdefault("BENCHMARKS_DISABLE_PUBLIC_SKILLS", "1")
    env.setdefault("BENCHMARKS_LIGHT_SYSTEM_PROMPT", "1")
    env.setdefault("BENCHMARKS_SHORT_TASK_PROMPT", "1")
    env.setdefault("PYTHONUTF8", "1")

    print("Running:")
    print(" ".join(cmd))
    cogtrace_status = "0" if args.no_cogtrace else "1"
    print(f"COGTRACE_ONLINE={cogtrace_status} COGTRACE_MODE={args.mode}")
    print(
        "BENCHMARKS_DISABLE_PUBLIC_SKILLS=1 BENCHMARKS_LIGHT_SYSTEM_PROMPT=1 "
        "BENCHMARKS_SHORT_TASK_PROMPT=1"
    )
    if args.dry_run:
        return
    subprocess.run(cmd, cwd=BENCHMARKS, env=env, check=True)


if __name__ == "__main__":
    main()
