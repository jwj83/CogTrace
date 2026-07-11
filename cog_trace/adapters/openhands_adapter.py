from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from cog_trace.adapters.base import TraceAdapter
from cog_trace.core.schema import TraceStep


def _content_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts: list[str] = []
        for item in value:
            if isinstance(item, dict):
                parts.append(str(item.get("text") or item.get("content") or ""))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or "")
    return str(value)


class OpenHandsAdapter(TraceAdapter):
    """Adapter for OpenHands conversation archives exported as events.jsonl."""

    def iter_steps(self, path: Path) -> list[TraceStep]:
        steps: list[TraceStep] = []
        with path.open("r", encoding="utf-8") as handle:
            for event_index, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                raw = json.loads(line)
                kind = raw.get("kind") or raw.get("event_type") or ""
                source = raw.get("source") or ""
                tool_name = raw.get("tool_name")
                thought = _content_text(raw.get("thought"))
                action = raw.get("action") or {}
                observation_obj = raw.get("observation") or {}
                message = ""
                if raw.get("llm_message"):
                    message = _content_text(raw["llm_message"].get("content"))

                action_command = ""
                action_path = ""
                if isinstance(action, dict):
                    action_command = str(action.get("command") or "")
                    action_path = str(action.get("path") or "")

                observation = ""
                if isinstance(observation_obj, dict):
                    observation = _content_text(observation_obj.get("content"))
                    if not observation:
                        observation = str(observation_obj.get("message") or "")
                    if not action_command:
                        action_command = str(observation_obj.get("command") or "")
                    if not action_path:
                        action_path = str(
                            observation_obj.get("path") or observation_obj.get("file_path") or ""
                        )
                    if isinstance(observation_obj.get("exit_code"), int):
                        raw["exit_code"] = observation_obj["exit_code"]

                steps.append(
                    TraceStep(
                        event_index=event_index,
                        kind=kind,
                        source=source,
                        tool_name=tool_name,
                        thought=thought,
                        action_command=action_command,
                        action_path=action_path,
                        observation=observation,
                        message=message,
                        raw=raw,
                    )
                )
        return steps
