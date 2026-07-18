"""Protocol for objects that expose a slug used in path-like completion."""

from __future__ import annotations

from typing import Protocol


class Sluggable(Protocol):
    """A board/column/task-like object with a slug attribute."""

    slug: str
