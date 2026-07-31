"""Tests for TaskFilter.matches, the predicate the service and TUI share."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from kanban.models import Priority, Slug, Task, TaskFilter


def make_task(**overrides: object) -> Task:
    """Return a task with predictable defaults, overridable field by field."""
    fields: dict[str, object] = {
        "id": uuid4(),
        "title": "Fix login bug",
        "slug": Slug("fix-login-bug"),
        "board": Slug("main"),
        "column": Slug("todo"),
        "assigned_to": "alice",
        "created_by": "mark",
        "priority": Priority.HIGH,
        "tags": ["bug", "auth"],
        "due_date": datetime(2026, 6, 15, tzinfo=timezone.utc),
    }
    fields.update(overrides)
    return Task(**fields)  # type: ignore[arg-type]


class TestEmptyFilter(unittest.TestCase):
    """A filter with nothing set matches everything."""

    def test_matches_any_task(self) -> None:
        """No criteria means no filtering."""
        self.assertTrue(TaskFilter().matches(make_task()))


class TestScalarCriteria(unittest.TestCase):
    """Assignee, priority, and creator are matched exactly."""

    def test_assigned_to_matches(self) -> None:
        """The assignee must be the one named."""
        self.assertTrue(TaskFilter(assigned_to="alice").matches(make_task()))

    def test_assigned_to_differs(self) -> None:
        """A different assignee excludes the task."""
        self.assertFalse(TaskFilter(assigned_to="bob").matches(make_task()))

    def test_priority_matches(self) -> None:
        """The priority must be the one named."""
        self.assertTrue(TaskFilter(priority=Priority.HIGH).matches(make_task()))

    def test_priority_differs(self) -> None:
        """A different priority excludes the task."""
        self.assertFalse(TaskFilter(priority=Priority.LOW).matches(make_task()))

    def test_created_by_matches(self) -> None:
        """The creator must be the one named."""
        self.assertTrue(TaskFilter(created_by="mark").matches(make_task()))


class TestTagCriteria(unittest.TestCase):
    """Tags match when the task carries any of them."""

    def test_single_tag(self) -> None:
        """A task with the tag matches."""
        self.assertTrue(TaskFilter(tags=["auth"]).matches(make_task()))

    def test_any_of_several_tags(self) -> None:
        """Several tags are combined with or."""
        self.assertTrue(TaskFilter(tags=["docs", "auth"]).matches(make_task()))

    def test_no_tag_in_common(self) -> None:
        """A task carrying none of the tags is excluded."""
        self.assertFalse(TaskFilter(tags=["docs"]).matches(make_task()))


class TestDueDateCriteria(unittest.TestCase):
    """Due-date bounds are exclusive on both sides."""

    def test_due_before(self) -> None:
        """A task due earlier than the bound matches."""
        bound = datetime(2026, 6, 20, tzinfo=timezone.utc)
        self.assertTrue(TaskFilter(due_before=bound).matches(make_task()))

    def test_due_before_excludes_later(self) -> None:
        """A task due after the bound is excluded."""
        bound = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.assertFalse(TaskFilter(due_before=bound).matches(make_task()))

    def test_due_after(self) -> None:
        """A task due later than the bound matches."""
        bound = datetime(2026, 6, 1, tzinfo=timezone.utc)
        self.assertTrue(TaskFilter(due_after=bound).matches(make_task()))

    def test_task_without_a_due_date(self) -> None:
        """A task with no due date cannot satisfy a date bound."""
        bound = datetime(2026, 6, 20, tzinfo=timezone.utc)
        self.assertFalse(TaskFilter(due_before=bound).matches(make_task(due_date=None)))


class TestExcludedColumns(unittest.TestCase):
    """Excluded columns remove their tasks."""

    def test_task_in_an_excluded_column(self) -> None:
        """A task in an excluded column is filtered out."""
        self.assertFalse(TaskFilter(exclude_columns=["todo"]).matches(make_task()))

    def test_task_in_another_column(self) -> None:
        """A task elsewhere is unaffected."""
        self.assertTrue(TaskFilter(exclude_columns=["done"]).matches(make_task()))


class TestCombinedCriteria(unittest.TestCase):
    """Every criterion that is set has to hold."""

    def test_all_criteria_satisfied(self) -> None:
        """A task meeting every criterion matches."""
        filter = TaskFilter(assigned_to="alice", priority=Priority.HIGH, tags=["auth"])
        self.assertTrue(filter.matches(make_task()))

    def test_one_criterion_failing_is_enough(self) -> None:
        """Failing a single criterion excludes the task."""
        filter = TaskFilter(assigned_to="alice", priority=Priority.LOW)
        self.assertFalse(filter.matches(make_task()))
