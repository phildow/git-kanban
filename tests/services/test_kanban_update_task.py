"""Tests for KanbanService.update_task, exercising every TaskUpdateParams flag."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Priority, Task
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.base import TaskNotFound
from kanban.storage.memory import InMemoryRepository


def _make_service() -> tuple[KanbanService, InMemoryRepository]:
    """Return a fresh KanbanService backed by an InMemoryRepository with an alpha board."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )
    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    repo.create_column("alpha", "done", slug="done")
    return svc, repo


class TestKanbanServiceUpdateTaskBasics(unittest.TestCase):
    """update_task returns the updated task and refreshes the index."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(
                title="fix-login",
                assigned_to="alice",
                priority=Priority.LOW,
                tags=["bug"],
                due_date=datetime(2026, 6, 20),
                created_by="alice",
                description="Initial description.",
            ),
        )
        self.svc.index_service.reset_mock()

    def test_returns_task_instance(self) -> None:
        """update_task returns a Task."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(assigned_to="bob"),
        )

        self.assertIsInstance(result, Task)

    def test_updates_index(self) -> None:
        """update_task calls index_service.upsert_task with the updated task."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(assigned_to="bob"),
        )

        self.svc.index_service.upsert_task.assert_called_once_with(result)

    def test_none_params_leaves_task_unchanged(self) -> None:
        """An update with all-None fields leaves the task's data intact."""
        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertEqual(result.title, "fix-login")
        self.assertEqual(result.assigned_to, "alice")
        self.assertEqual(result.priority, Priority.LOW)
        self.assertEqual(result.tags, ["bug"])
        self.assertEqual(result.due_date, datetime(2026, 6, 20))
        self.assertEqual(result.created_by, "alice")


class TestKanbanServiceUpdateTaskTitle(unittest.TestCase):
    """The title flag renames the task and re-slugs the filename."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_title_is_stored(self) -> None:
        """update_task changes the task's title to the supplied value."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(title="Fix Login Bug"),
        )

        self.assertEqual(result.title, "Fix Login Bug")

    def test_slug_is_reslugged_from_new_title(self) -> None:
        """A new title updates the task's slug to match."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(title="Fix Login Bug"),
        )

        self.assertEqual(result.slug, "fix-login-bug")

    def test_task_is_retrievable_under_new_slug(self) -> None:
        """After rename the task can be fetched by its new slug."""
        self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(title="Fix Login Bug"),
        )

        fetched = self.repo.get_task("alpha", "todo", "fix-login-bug")
        self.assertEqual(fetched.title, "Fix Login Bug")

    def test_same_title_is_a_noop(self) -> None:
        """Supplying the current title as the new title leaves the slug unchanged."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(title="fix-login"),
        )

        self.assertEqual(result.slug, "fix-login")


class TestKanbanServiceUpdateTaskAssignedTo(unittest.TestCase):
    """The assigned_to flag reassigns the task."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_assigned_to_is_stored(self) -> None:
        """update_task sets assigned_to to the supplied value."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(assigned_to="bob"),
        )

        self.assertEqual(result.assigned_to, "bob")

    def test_assigned_to_none_leaves_current_value(self) -> None:
        """A None assigned_to means "no change" for the assignee field."""
        self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(assigned_to="bob"),
        )

        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertEqual(result.assigned_to, "bob")


class TestKanbanServiceUpdateTaskPriority(unittest.TestCase):
    """The priority flag updates the task's priority."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_priority_is_stored(self) -> None:
        """update_task sets priority to the supplied Priority."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(priority=Priority.HIGH),
        )

        self.assertEqual(result.priority, Priority.HIGH)

    def test_priority_none_leaves_current_value(self) -> None:
        """A None priority means "no change" for the priority field."""
        self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(priority=Priority.HIGH),
        )

        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertEqual(result.priority, Priority.HIGH)


class TestKanbanServiceUpdateTaskTags(unittest.TestCase):
    """The tags flag merges new tags into the task's tag list."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", tags=["bug"]),
        )

    def test_new_tag_is_appended(self) -> None:
        """A tag not currently on the task is added to the tag list."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(tags=["auth"]),
        )

        self.assertEqual(sorted(result.tags), ["auth", "bug"])

    def test_existing_tag_is_not_duplicated(self) -> None:
        """A tag already on the task is not added a second time."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(tags=["bug"]),
        )

        self.assertEqual(result.tags, ["bug"])

    def test_tags_none_leaves_current_tags(self) -> None:
        """A None tags list means "no change" for the tag list."""
        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertEqual(result.tags, ["bug"])


class TestKanbanServiceUpdateTaskDueDate(unittest.TestCase):
    """The due_date flag updates the task's due date."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_due_date_datetime_is_stored(self) -> None:
        """A datetime due_date is stored on the task."""
        due = datetime(2026, 6, 20)
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(due_date=due),
        )

        self.assertEqual(result.due_date, due)

    def test_due_date_iso_string_is_parsed(self) -> None:
        """A due_date supplied as an ISO string is parsed to a datetime."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(due_date="2026-06-20T00:00:00"),
        )

        self.assertEqual(result.due_date, datetime(2026, 6, 20))

    def test_due_date_none_leaves_current_value(self) -> None:
        """A None due_date means "no change" for the due date."""
        self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(due_date=datetime(2026, 6, 20)),
        )

        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertEqual(result.due_date, datetime(2026, 6, 20))


class TestKanbanServiceUpdateTaskCreatedBy(unittest.TestCase):
    """The created_by flag updates the task's creator."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_created_by_is_stored(self) -> None:
        """update_task sets created_by to the supplied value."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(created_by="bob"),
        )

        self.assertEqual(result.created_by, "bob")

    def test_created_by_none_leaves_current_value(self) -> None:
        """A None created_by means "no change" for the created_by field."""
        self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(created_by="bob"),
        )

        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertEqual(result.created_by, "bob")


class TestKanbanServiceUpdateTaskDescription(unittest.TestCase):
    """The description flag rewrites the task body's Description section."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", description="original"),
        )

    def test_description_is_written_to_body(self) -> None:
        """A new description replaces the Description section content."""
        result = self.svc.update_task(
            "alpha/todo/fix-login",
            TaskUpdateParams(description="updated"),
        )

        self.assertIn("# Description", result.body)
        self.assertIn("updated", result.body)
        self.assertNotIn("original", result.body)

    def test_description_none_leaves_body_untouched(self) -> None:
        """A None description means "no change" for the task body."""
        result = self.svc.update_task("alpha/todo/fix-login", TaskUpdateParams())

        self.assertIn("original", result.body)


class TestKanbanServiceUpdateTaskActiveBoard(unittest.TestCase):
    """update_task can resolve a bare task slug against the active board."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.working_board = "alpha"

    def test_bare_task_slug_resolves_against_active_board(self) -> None:
        """A bare task slug resolves to its column within the active board."""
        result = self.svc.update_task("fix-login", TaskUpdateParams(assigned_to="alice"))

        self.assertEqual(result.assigned_to, "alice")


class TestKanbanServiceUpdateTaskErrors(unittest.TestCase):
    """update_task raises when the task cannot be resolved."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_raises_for_missing_task(self) -> None:
        """update_task raises TaskNotFound when no task matches the path."""
        with self.assertRaises(TaskNotFound):
            self.svc.update_task(
                "alpha/todo/missing",
                TaskUpdateParams(assigned_to="alice"),
            )


if __name__ == "__main__":
    unittest.main()
