from __future__ import annotations

import json

from cog_trace.adapters.openhands_adapter import OpenHandsAdapter
from cog_trace.trajectory.normalize import normalize_trace_step


def test_observation_command_is_preserved_for_test_detection(tmp_path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "obs",
                "kind": "ObservationEvent",
                "source": "environment",
                "tool_name": "terminal",
                "observation": {
                    "content": [{"text": "2 passed"}],
                    "command": "python -m pytest tests/test_parser.py",
                    "exit_code": 0,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    step = OpenHandsAdapter().iter_steps(path)[0]
    event = normalize_trace_step(step)
    assert event.type == "test"
    assert event.test_passed is True
    assert event.exit_code == 0
