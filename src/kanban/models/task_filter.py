from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .priority import Priority
from .slug import Slug
from .task import Task


@dataclass
class TaskFilter:
    """Optional criteria for narrowing task lists and search results.

    All fields are optional; `None` means "do not filter by this field".

    `include_archived` is the exception to that: archived tasks are left out
    unless it is set, so the filter a caller builds without thinking about the
    archive is one that does not carry it.  Whether a task is archived is a
    question about its column's role, which a task alone cannot answer, so the
    service applies this field where it knows the board rather than `matches`.
    """

    assigned_to:      str | None = None
    priority:         Priority | None = None
    tags:             list[str] = field(default_factory=list)
    due_before:       datetime | None = None
    due_after:        datetime | None = None
    created_by:       str | None = None
    exclude_columns:  list[Slug] = field(default_factory=list)
    include_archived: bool = False

    def matches(self, task: Task) -> bool:
        """
        Return True when `task` satisfies every criterion that is set.

        The filter owns this rather than any one caller, so the service and the
        TUI agree on what a filter means.  `include_archived` is not among them:
        it needs the board's columns, so the service applies it.
        """
        if self.assigned_to is not None and task.assigned_to != self.assigned_to:
            return False
        if self.priority is not None and task.priority != self.priority:
            return False
        if self.tags and not any(tag in task.tags for tag in self.tags):
            return False
        if self.created_by is not None and task.created_by != self.created_by:
            return False
        if self.due_before is not None and (
            task.due_date is None or task.due_date >= self.due_before
        ):
            return False
        if self.due_after is not None and (
            task.due_date is None or task.due_date <= self.due_after
        ):
            return False
        if self.exclude_columns and task.column in self.exclude_columns:
            return False
        return True
