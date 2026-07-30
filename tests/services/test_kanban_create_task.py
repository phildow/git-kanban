"""Tests for KanbanService.create_task, exercising every TaskCreateParams flag."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock
from uuid import UUID
from uuid import uuid4

from kanban.models import Priority, Task
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.base import BoardNotFound, ColumnNotFound, TaskAlreadyExists
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


class TestKanbanServiceCreateTaskBasics(unittest.TestCase):
    """create_task returns a Task placed in the requested board/column."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()

    def test_returns_task_instance(self) -> None:
        """create_task returns a Task."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertIsInstance(task, Task)

    def test_assigns_uuid_id(self) -> None:
        """The created task has a fresh UUID as its id."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertIsInstance(task.id, UUID)

    def test_records_board_and_column(self) -> None:
        """The task's board and column reflect the path."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertEqual(task.board, "alpha")
        self.assertEqual(task.column, "todo")

    def test_persists_task_in_repository(self) -> None:
        """The created task is retrievable from the repository."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        fetched = self.repo.get_task("alpha", "todo", "fix-login")
        self.assertEqual(fetched.slug, "fix-login")

    def test_updates_index(self) -> None:
        """create_task calls index_service.upsert_task with the created task."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.svc.index_service.upsert_task.assert_called_once_with(task)


class TestKanbanServiceCreateTaskTitle(unittest.TestCase):
    """The title flag is preserved and used to derive the slug."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_title_is_stored_unchanged(self) -> None:
        """The task's title matches the supplied title exactly."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="Fix Login Bug"))

        self.assertEqual(task.title, "Fix Login Bug")

    def test_slug_is_derived_from_title(self) -> None:
        """The task's slug is a kebab-cased slug of the title."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="Fix Login Bug"))

        self.assertEqual(task.slug, "fix-login-bug")


class TestKanbanServiceCreateTaskAssignedTo(unittest.TestCase):
    """The assigned_to flag records an assignee on the new task."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_assigned_to_is_stored(self) -> None:
        """The task's assigned_to matches the supplied value."""
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", assigned_to="alice"),
        )

        self.assertEqual(task.assigned_to, "alice")

    def test_assigned_to_defaults_to_none(self) -> None:
        """When no assignee is supplied assigned_to is None."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertIsNone(task.assigned_to)


class TestKanbanServiceCreateTaskPriority(unittest.TestCase):
    """The priority flag records a Priority on the new task."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_priority_is_stored(self) -> None:
        """The task's priority matches the supplied Priority."""
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", priority=Priority.HIGH),
        )

        self.assertEqual(task.priority, Priority.HIGH)

    def test_priority_defaults_to_none(self) -> None:
        """When no priority is supplied priority is None."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertIsNone(task.priority)


class TestKanbanServiceCreateTaskTags(unittest.TestCase):
    """The tags flag records a tag list on the new task."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_tags_are_stored(self) -> None:
        """The task's tags match the supplied list."""
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", tags=["bug", "auth"]),
        )

        self.assertEqual(task.tags, ["bug", "auth"])

    def test_tags_default_to_empty_list(self) -> None:
        """When no tags are supplied tags is an empty list."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertEqual(task.tags, [])


class TestKanbanServiceCreateTaskDueDate(unittest.TestCase):
    """The due_date flag records a datetime on the new task."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_due_date_datetime_is_stored(self) -> None:
        """A datetime due_date is stored on the task."""
        due = datetime(2026, 6, 20)
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", due_date=due),
        )

        self.assertEqual(task.due_date, due)

    def test_due_date_iso_string_is_parsed(self) -> None:
        """A due_date supplied as an ISO string is parsed to a datetime."""
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", due_date="2026-06-20T00:00:00"),
        )

        self.assertEqual(task.due_date, datetime(2026, 6, 20))

    def test_due_date_defaults_to_none(self) -> None:
        """When no due_date is supplied due_date is None."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertIsNone(task.due_date)


class TestKanbanServiceCreateTaskCreatedBy(unittest.TestCase):
    """The created_by flag records the creator on the new task."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_created_by_is_stored(self) -> None:
        """The task's created_by matches the supplied value."""
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", created_by="bob"),
        )

        self.assertEqual(task.created_by, "bob")

    def test_created_by_defaults_to_none(self) -> None:
        """When no creator is supplied created_by is None."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertIsNone(task.created_by)


class TestKanbanServiceCreateTaskDescription(unittest.TestCase):
    """The description flag populates the task body's Description section."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_description_is_written_to_body(self) -> None:
        """The description appears under the Description heading in the body."""
        task = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login", description="Fix the failing login flow."),
        )

        self.assertIn("# Description", task.body)
        self.assertIn("Fix the failing login flow.", task.body)

    def test_description_defaults_to_empty_body_with_heading(self) -> None:
        """Without a description the body still has the Description heading."""
        task = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        self.assertEqual(task.body, "# Description\n\n")


class TestKanbanServiceCreateTaskActiveBoard(unittest.TestCase):
    """create_task can resolve a bare column slug against the active board."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_active_board_resolves_bare_column_slug(self) -> None:
        """With an active board a column-only path lands the task on that board."""
        self.svc.working_board = "alpha"

        task = self.svc.create_task("todo", TaskCreateParams(title="fix-login"))

        self.assertEqual(task.board, "alpha")
        self.assertEqual(task.column, "todo")


class TestKanbanServiceCreateTaskErrors(unittest.TestCase):
    """create_task raises for invalid paths, missing locations, and duplicates."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()

    def test_raises_without_column_in_path(self) -> None:
        """create_task raises ValueError when the path has no column component."""
        with self.assertRaises(ValueError):
            self.svc.create_task(Path("/alpha"), TaskCreateParams(title="fix-login"))

    def test_raises_for_missing_board(self) -> None:
        """create_task raises BoardNotFound when the target board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.create_task("missing/todo", TaskCreateParams(title="fix-login"))

    def test_raises_for_missing_column(self) -> None:
        """create_task raises ColumnNotFound when the target column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.svc.create_task("alpha/missing", TaskCreateParams(title="fix-login"))

    def test_raises_when_task_slug_already_exists_in_board(self) -> None:
        """create_task raises TaskAlreadyExists when the slug is taken on the board."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        with self.assertRaises(TaskAlreadyExists):
            self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_raises_when_task_slug_exists_in_another_column(self) -> None:
        """create_task raises TaskAlreadyExists for a duplicate slug in any column."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        with self.assertRaises(TaskAlreadyExists):
            self.svc.create_task("alpha/done", TaskCreateParams(title="fix-login"))


if __name__ == "__main__":
    unittest.main()
