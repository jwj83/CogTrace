from __future__ import annotations

import re
from pathlib import PurePosixPath

from cog_trace.core.schema import NormalizedEvent, TraceStep

_TEST_COMMAND = re.compile(r"(?:^|\s)(?:pytest|python\s+-m\s+(?:pytest|unittest))\b", re.I)
_FAIL = re.compile(r"\b(?:failed|failure|assertionerror|traceback|error)\b", re.I)
_PASS = re.compile(r"\b(?:passed|success|\bok\b)\b", re.I)
_ENVIRONMENT_ERROR = re.compile(
    r"\b(?:modulenotfounderror|importerror|command not found|not installed|no module named)\b",
    re.I,
)
_EDIT_COMMAND = re.compile(r"\b(?:str_replace|insert|create|write|apply_patch|sed\s+-i)\b", re.I)
_PATH = re.compile(
    r"(?P<path>(?:[A-Za-z]:\\|/)[^\s`'\",)]+\.(?:py|js|ts|tsx|java|go|rs|md|toml|yaml|yml))"
)


def _normalise_path(path: str) -> str:
    path = path.strip().replace("\\", "/")
    try:
        return str(PurePosixPath(path))
    except ValueError:
        return path


def normalize_trace_step(step: TraceStep) -> NormalizedEvent:
    tool = (step.tool_name or "").lower()
    command = step.action_command.strip()
    raw_text = step.text or command or str(step.raw)
    combined = "\n".join(part for part in (raw_text, command, step.action_path) if part)
    files = {_normalise_path(path) for path in _PATH.findall(combined)}
    if step.action_path:
        files.add(_normalise_path(step.action_path))

    event_type = "thought"
    test_passed: bool | None = None
    test_failed: bool | None = None
    is_environment_error = False

    if step.kind == "MessageEvent" and step.source == "user":
        event_type = "issue"
    elif tool == "finish":
        event_type = "finish"
    elif tool == "file_editor" or _EDIT_COMMAND.search(command):
        event_type = "action"
    elif _TEST_COMMAND.search(command):
        event_type = "test" if step.observation else "action"
        if step.observation:
            is_environment_error = bool(_ENVIRONMENT_ERROR.search(step.observation))
            if _FAIL.search(step.observation):
                test_failed = True
            elif _PASS.search(step.observation):
                test_passed = True
    elif step.kind == "ObservationEvent" or step.observation:
        event_type = "observation"
    elif step.kind == "ActionEvent" or tool:
        event_type = "action"

    raw_id = step.raw.get("id") if isinstance(step.raw, dict) else None
    event_id = str(raw_id or f"event-{step.event_index}")
    exit_code = None
    if isinstance(step.raw, dict):
        value = step.raw.get("exit_code")
        if isinstance(value, int):
            exit_code = value

    return NormalizedEvent(
        event_id=event_id,
        step_id=step.event_index,
        type=event_type,  # type: ignore[arg-type]
        raw_text=raw_text,
        files=tuple(sorted(files)),
        command=command,
        tool_name=step.tool_name or "",
        exit_code=exit_code,
        test_passed=test_passed,
        test_failed=test_failed,
        is_environment_error=is_environment_error,
        metadata={
            "source": step.source,
            "kind": step.kind,
            "thought": step.thought,
        },
    )
