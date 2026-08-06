"""Tests for KanbanService.delete_task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Slug, Task
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
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
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )
    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    repo.create_column("alpha", "done", slug="done")
    return svc, repo


class TestKanbanServiceDeleteTaskBasics(unittest.TestCase):
    """delete_task returns the deleted task and removes it from the index."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.created = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login"),
        )
        self.svc.index_service.reset_mock()

    def test_returns_task_instance(self) -> None:
        """delete_task returns a Task."""
        result = self.svc.delete_task("alpha/todo/fix-login")

        self.assertIsInstance(result, Task)

    def test_returns_the_deleted_task(self) -> None:
        """The returned Task matches the one that was created."""
        result = self.svc.delete_task("alpha/todo/fix-login")

        self.assertEqual(result.id, self.created.id)
        self.assertEqual(result.slug, "fix-login")

    def test_updates_index(self) -> None:
        """delete_task calls index_service.remove_task with the deleted task."""
        result = self.svc.delete_task("alpha/todo/fix-login")

        self.svc.index_service.remove_task.assert_called_once_with(result)


class TestKanbanServiceDeleteTaskRemoval(unittest.TestCase):
    """delete_task removes the task from the repository."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_task_is_no_longer_in_repository(self) -> None:
        """After delete the task cannot be fetched from its column."""
        self.svc.delete_task("alpha/todo/fix-login")

        with self.assertRaises(TaskNotFound):
            self.repo.get_task("alpha", "todo", "fix-login")

    def test_task_is_removed_from_column_task_list(self) -> None:
        """After delete the column no longer lists the task."""
        self.svc.delete_task("alpha/todo/fix-login")

        slugs = [t.slug for t in self.repo.get_tasks("alpha", "todo")]
        self.assertNotIn("fix-login", slugs)

    def test_other_tasks_are_unaffected(self) -> None:
        """Deleting one task does not remove sibling tasks."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        self.svc.delete_task("alpha/todo/fix-login")

        slugs = [t.slug for t in self.repo.get_tasks("alpha", "todo")]
        self.assertEqual(slugs, ["write-docs"])


class TestKanbanServiceDeleteTaskActiveBoard(unittest.TestCase):
    """delete_task can resolve a bare task slug against the active board."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.working_board = "alpha"

    def test_bare_task_slug_resolves_against_active_board(self) -> None:
        """A bare task slug is resolved to its column within the active board."""
        result = self.svc.delete_task(Slug("fix-login"))

        self.assertEqual(result.slug, "fix-login")
        with self.assertRaises(TaskNotFound):
            self.repo.get_task("alpha", "todo", "fix-login")


class TestKanbanServiceDeleteTaskErrors(unittest.TestCase):
    """delete_task raises when the task cannot be resolved."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_raises_for_missing_task(self) -> None:
        """delete_task raises TaskNotFound when no task matches the path."""
        with self.assertRaises(TaskNotFound):
            self.svc.delete_task("alpha/todo/missing")

    def test_raises_for_missing_bare_slug(self) -> None:
        """delete_task raises TaskNotFound when a bare slug matches no task."""
        self.svc.working_board = "alpha"

        with self.assertRaises(TaskNotFound):
            self.svc.delete_task(Slug("missing"))


if __name__ == "__main__":
    unittest.main()
