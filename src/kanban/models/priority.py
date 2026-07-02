from __future__ import annotations

from enum import StrEnum


class Priority(StrEnum):
    """A task's priority level."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


PRIORITY_ORDER: dict[Priority, int] = {
    Priority.LOW: 0,
    Priority.MEDIUM: 1,
    Priority.HIGH: 2,
}
