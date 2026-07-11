from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from cog_trace.core.schema import TraceStep


class TraceAdapter(ABC):
    @abstractmethod
    def iter_steps(self, path: Path) -> list[TraceStep]:
        """Convert an agent-specific trace into normalized TraceStep objects."""
        raise NotImplementedError
