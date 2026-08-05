"""Tests for KanbanService.move_task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Slug, Task
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.base import BoardNotFound, ColumnNotFound, TaskNotFound
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


class TestKanbanServiceMoveTaskBasics(unittest.TestCase):
    """move_task returns the moved task and refreshes the index."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.created = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login"),
        )
        self.svc.index_service.reset_mock()

    def test_returns_task_instance(self) -> None:
        """move_task returns a Task."""
        result = self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        self.assertIsInstance(result, Task)

    def test_preserves_task_id(self) -> None:
        """move_task keeps the task's UUID unchanged."""
        result = self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        self.assertEqual(result.id, self.created.id)

    def test_updates_index(self) -> None:
        """move_task calls index_service.upsert_task with the moved task."""
        result = self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        self.svc.index_service.upsert_task.assert_called_once_with(result)


class TestKanbanServiceMoveTaskColumn(unittest.TestCase):
    """move_task relocates the task to the destination column."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_column_field_is_updated(self) -> None:
        """The returned task reports the destination column."""
        result = self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        self.assertEqual(result.column, "done")

    def test_board_is_unchanged(self) -> None:
        """move_task does not change the task's board."""
        result = self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        self.assertEqual(result.board, "alpha")

    def test_task_is_retrievable_in_destination_column(self) -> None:
        """After move the task is retrievable from the destination column."""
        self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        fetched = self.repo.get_task("alpha", "done", "fix-login")
        self.assertEqual(fetched.slug, "fix-login")

    def test_task_is_no_longer_in_source_column(self) -> None:
        """After move the task is no longer in the source column."""
        self.svc.move_task("alpha/todo/fix-login", Slug("done"))

        with self.assertRaises(TaskNotFound):
            self.repo.get_task("alpha", "todo", "fix-login")

    def test_move_to_same_column_is_idempotent(self) -> None:
        """Moving a task to its current column leaves it in place."""
        result = self.svc.move_task("alpha/todo/fix-login", Slug("todo"))

        self.assertEqual(result.column, "todo")
        fetched = self.repo.get_task("alpha", "todo", "fix-login")
        self.assertEqual(fetched.id, result.id)


class TestKanbanServiceMoveTaskActiveBoard(unittest.TestCase):
    """move_task can resolve a bare task slug against the active board."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.working_board = "alpha"

    def test_bare_task_slug_resolves_against_active_board(self) -> None:
        """A bare task slug is resolved to its column within the active board."""
        result = self.svc.move_task(Slug("fix-login"), Slug("done"))

        self.assertEqual(result.column, "done")


class TestKanbanServiceMoveTaskBoard(unittest.TestCase):
    """move_task sends a task to another board when one is named."""

    def setUp(self) -> None:
        self.svc, self.repo = _make_service()
        self.repo.create_board("beta", slug="beta")
        self.repo.create_column("beta", "todo", slug="todo")
        self.created = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(title="fix-login"),
        )

    def test_board_field_is_updated(self) -> None:
        """The returned task reports the destination board."""
        result = self.svc.move_task(
            "alpha/todo/fix-login", Slug("todo"), Slug("beta")
        )

        self.assertEqual(result.board, "beta")

    def test_column_field_is_updated(self) -> None:
        """The returned task reports the destination column on that board."""
        result = self.svc.move_task(
            "alpha/todo/fix-login", Slug("todo"), Slug("beta")
        )

        self.assertEqual(result.column, "todo")

    def test_preserves_task_id(self) -> None:
        """Crossing boards keeps the task's UUID unchanged."""
        result = self.svc.move_task(
            "alpha/todo/fix-login", Slug("todo"), Slug("beta")
        )

        self.assertEqual(result.id, self.created.id)

    def test_task_is_retrievable_on_destination_board(self) -> None:
        """After the move the task is retrievable from the destination board."""
        self.svc.move_task("alpha/todo/fix-login", Slug("todo"), Slug("beta"))

        fetched = self.repo.get_task("beta", "todo", "fix-login")
        self.assertEqual(fetched.slug, "fix-login")

    def test_task_is_no_longer_on_source_board(self) -> None:
        """After the move the task is gone from the column it left."""
        self.svc.move_task("alpha/todo/fix-login", Slug("todo"), Slug("beta"))

        with self.assertRaises(TaskNotFound):
            self.repo.get_task("alpha", "todo", "fix-login")

    def test_updates_index(self) -> None:
        """Crossing boards refreshes the task's index entry."""
        result = self.svc.move_task(
            "alpha/todo/fix-login", Slug("todo"), Slug("beta")
        )

        self.svc.index_service.upsert_task.assert_called_with(result)

    def test_raises_for_missing_destination_board(self) -> None:
        """move_task raises BoardNotFound when the destination board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.move_task(
                "alpha/todo/fix-login", Slug("todo"), Slug("missing")
            )

    def test_raises_for_column_missing_on_destination_board(self) -> None:
        """move_task raises ColumnNotFound when the destination board has no such column."""
        with self.assertRaises(ColumnNotFound):
            self.svc.move_task(
                "alpha/todo/fix-login", Slug("done"), Slug("beta")
            )


class TestKanbanServiceMoveTaskErrors(unittest.TestCase):
    """move_task raises when the task or destination column cannot be resolved."""

    def setUp(self) -> None:
        self.svc, _ = _make_service()
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

    def test_raises_for_missing_task(self) -> None:
        """move_task raises TaskNotFound when no task matches the path."""
        with self.assertRaises(TaskNotFound):
            self.svc.move_task("alpha/todo/missing", Slug("done"))

    def test_raises_for_missing_destination_column(self) -> None:
        """move_task raises ColumnNotFound when the destination column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.svc.move_task("alpha/todo/fix-login", Slug("missing"))


if __name__ == "__main__":
    unittest.main()
