from __future__ import annotations

from dataclasses import dataclass, field

from cog_trace.core.schema import NormalizedEvent


@dataclass
class ExtractionPolicy:
    max_buffer_events: int = 8
    max_buffer_tokens: int = 1500
    _buffer: list[NormalizedEvent] = field(default_factory=list)
    _estimated_tokens: int = 0
    _in_edit_burst: bool = False
    _seen_issue: bool = False

    def observe(self, event: NormalizedEvent) -> tuple[bool, list[str]]:
        self._buffer.append(event)
        self._estimated_tokens += max(1, len(event.raw_text) // 4)
        reasons: list[str] = []
        if event.type == "issue" and not self._seen_issue:
            reasons.append("task_start")
            self._seen_issue = True
        if event.type == "action" and self._is_edit(event) and not self._in_edit_burst:
            reasons.append("new_edit_burst")
            self._in_edit_burst = True
        elif event.type not in {"action", "diff"}:
            self._in_edit_burst = False
        if event.type == "test" and not event.is_environment_error:
            reasons.append("functional_test_result")
        if event.type == "finish":
            reasons.append("finish")
        if len(self._buffer) >= self.max_buffer_events:
            reasons.append("event_buffer_limit")
        if self._estimated_tokens >= self.max_buffer_tokens:
            reasons.append("token_buffer_limit")
        return bool(reasons), reasons

    def pop_buffer(self) -> list[NormalizedEvent]:
        events = self._buffer
        self._buffer = []
        self._estimated_tokens = 0
        return events

    @staticmethod
    def _is_edit(event: NormalizedEvent) -> bool:
        command = event.command.lower()
        return event.tool_name.lower() == "file_editor" or any(
            marker in command
            for marker in ("str_replace", "insert", "create", "write", "apply_patch")
        )
