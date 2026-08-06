"""Tests for KanbanService.rename_task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Slug, Task
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.base import TaskAlreadyExists, TaskNotFound
from kanban.storage.memory import InMemoryRepository


def _make_service() -> tuple[KanbanService, InMemoryRepository]:
    """Return a fresh KanbanService backed by an InMemoryRepository with an alpha board."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )
    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    repo.create_column("alpha", "done", slug="done")
    return svc, repo


class TestKanbanServiceRenameTaskBasics(unittest.TestCase):
    """rename_task returns the renamed Task and refreshes the index."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.created = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login"),
        )
        self.svc.index_service.reset_mock()

    def test_returns_task_instance(self) -> None:
        """rename_task returns a Task."""
        result = self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        self.assertIsInstance(result, Task)

    def test_preserves_task_id(self) -> None:
        """rename_task keeps the task's UUID unchanged."""
        result = self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        self.assertEqual(result.id, self.created.id)

    def test_updates_index(self) -> None:
        """rename_task calls index_service.upsert_task with the renamed task."""
        result = self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        self.svc.index_service.upsert_task.assert_called_once_with(result)


class TestKanbanServiceRenameTaskTitle(unittest.TestCase):
    """rename_task updates the task's title and slug."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_title_is_stored(self) -> None:
        """The task's title is set to the supplied new title."""
        result = self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        self.assertEqual(result.title, "Fix Login Bug")

    def test_slug_is_reslugged_from_new_title(self) -> None:
        """The task's slug is derived from the new title."""
        result = self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        self.assertEqual(result.slug, "fix-login-bug")

    def test_board_and_column_are_unchanged(self) -> None:
        """rename_task leaves the task's board and column intact."""
        result = self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        self.assertEqual(result.board, "alpha")
        self.assertEqual(result.column, "todo")

    def test_task_is_retrievable_under_new_slug(self) -> None:
        """After rename the task can be fetched by its new slug."""
        self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        fetched = self.repo.get_task("alpha", "todo", "fix-login-bug")
        self.assertEqual(fetched.title, "Fix Login Bug")

    def test_task_is_not_retrievable_under_old_slug(self) -> None:
        """After rename the old slug no longer resolves to a task."""
        self.svc.rename_task("alpha/todo/fix-login", "Fix Login Bug")

        with self.assertRaises(TaskNotFound):
            self.repo.get_task("alpha", "todo", "fix-login")


class TestKanbanServiceRenameTaskActiveBoard(unittest.TestCase):
    """rename_task can resolve a bare task slug against the active board."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.working_board = "alpha"

    def test_bare_task_slug_resolves_against_active_board(self) -> None:
        """A bare task slug is resolved to its column within the active board."""
        result = self.svc.rename_task(Slug("fix-login"), "Fix Login Bug")

        self.assertEqual(result.title, "Fix Login Bug")
        self.assertEqual(result.slug, "fix-login-bug")


class TestKanbanServiceRenameTaskErrors(unittest.TestCase):
    """rename_task raises when the task cannot be resolved or the new slug collides."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

    def test_raises_for_missing_task(self) -> None:
        """rename_task raises TaskNotFound when no task matches the path."""
        with self.assertRaises(TaskNotFound):
            self.svc.rename_task("alpha/todo/missing", "Anything")

    def test_raises_when_new_slug_collides_in_same_column(self) -> None:
        """rename_task raises TaskAlreadyExists when the new slug is taken in the column."""
        with self.assertRaises(TaskAlreadyExists):
            self.svc.rename_task("alpha/todo/fix-login", "write-docs")


if __name__ == "__main__":
    unittest.main()
