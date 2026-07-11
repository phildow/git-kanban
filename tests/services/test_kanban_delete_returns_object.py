"""Tests that KanbanService.delete_board/delete_column/delete_task return the deleted object."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Board, Column, Task
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceDeleteReturnsObject(unittest.TestCase):
    """delete_board/delete_column/delete_task return the deleted domain object."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
        )
        self.repo.create_board("My Project", slug="my-project")
        self.repo.create_column("my-project", "To Do", slug="todo")
        self.repo.create_column("my-project", "Done", slug="done")

    def test_delete_task_returns_deleted_task(self) -> None:
        """delete_task returns the Task that was removed, not None."""
        created = self.svc.create_task("my-project/todo/Fix login", TaskCreateParams())
        deleted = self.svc.delete_task("my-project/todo/fix-login")

        self.assertIsInstance(deleted, Task)
        self.assertEqual(deleted.id, created.id)
        self.assertEqual(deleted.title, "Fix login")

    def test_delete_task_removes_it_from_repository(self) -> None:
        """The task is actually gone after delete_task returns it."""
        self.svc.create_task("my-project/todo/Fix login", TaskCreateParams())
        self.svc.delete_task("my-project/todo/fix-login")

        self.assertEqual(self.svc.get_tasks("my-project/todo"), [])

    def test_delete_column_returns_deleted_column(self) -> None:
        """delete_column returns the Column that was removed, not None."""
        deleted = self.svc.delete_column("my-project/done")

        self.assertIsInstance(deleted, Column)
        self.assertEqual(deleted.slug, "done")
        self.assertEqual(deleted.name, "Done")

    def test_delete_column_removes_it_from_repository(self) -> None:
        """The column is actually gone after delete_column returns it."""
        self.svc.delete_column("my-project/done")

        slugs = [c.slug for c in self.svc.get_columns("my-project")]
        self.assertNotIn("done", slugs)

    def test_delete_board_returns_deleted_board(self) -> None:
        """delete_board returns the Board that was removed, not just its slug."""
        deleted = self.svc.delete_board("my-project")

        self.assertIsInstance(deleted, Board)
        self.assertEqual(deleted.slug, "my-project")
        self.assertEqual(deleted.name, "My Project")

    def test_delete_board_removes_it_from_repository(self) -> None:
        """The board is actually gone after delete_board returns it."""
        self.svc.delete_board("my-project")

        self.assertFalse(self.repo.board_exists("my-project"))


if __name__ == "__main__":
    unittest.main()
