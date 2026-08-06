"""Where a task is moved to within its column."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any


class ReorderOp(StrEnum):
    """
    The operations `reorder_task` accepts.

    `above` and `below` position a task against another task in its column and
    are the only ones that take a task to position against.
    """

    UP = "up"
    DOWN = "down"
    TOP = "top"
    BOTTOM = "bottom"
    ABOVE = "above"
    BELOW = "below"

    @classmethod
    def from_flags(cls, flags: Mapping[str, Any]) -> ReorderOp | None:
        """
        Return the operation whose flag is set, or None when none of them is.

        The move commands name their flags for the operations they run —
        `--top`, `--up` — so a flag that is set names its operation.  Flags
        that name none of them are passed over, which is what lets a whole
        command's arguments be handed in.
        """
        return next((op for op in cls if flags.get(op.value)), None)


"""The operations that position a task against another task in its column."""
RELATIVE_OPS: frozenset[ReorderOp] = frozenset({ReorderOp.ABOVE, ReorderOp.BELOW})
