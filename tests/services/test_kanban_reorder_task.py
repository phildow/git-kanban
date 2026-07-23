"""Tests for KanbanService.reorder_task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceReorderTask(unittest.TestCase):
    """KanbanService.reorder_task changes task position within its column."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.svc.create_task("alpha/todo", TaskCreateParams(title="first"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="second"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="third"))

    def _slugs(self) -> list[str]:
        return [t.slug for t in self.svc.get_tasks("alpha/todo")]

    def test_up_moves_task_one_position_earlier(self) -> None:
        """'up' moves the target task one position toward the front of the column."""
        self.svc.reorder_task(Path("alpha/todo/second"), "up")
        self.assertEqual(self._slugs(), ["second", "first", "third"])

    def test_down_moves_task_one_position_later(self) -> None:
        """'down' moves the target task one position toward the end of the column."""
        self.svc.reorder_task(Path("alpha/todo/second"), "down")
        self.assertEqual(self._slugs(), ["first", "third", "second"])

    def test_top_moves_task_to_first_position(self) -> None:
        """'top' places the target task at the front of the column."""
        self.svc.reorder_task(Path("alpha/todo/third"), "top")
        self.assertEqual(self._slugs(), ["third", "first", "second"])

    def test_bottom_moves_task_to_last_position(self) -> None:
        """'bottom' places the target task at the end of the column."""
        self.svc.reorder_task(Path("alpha/todo/first"), "bottom")
        self.assertEqual(self._slugs(), ["second", "third", "first"])

    def test_up_at_top_is_noop(self) -> None:
        """'up' on the first task leaves the column order unchanged."""
        self.svc.reorder_task(Path("alpha/todo/first"), "up")
        self.assertEqual(self._slugs(), ["first", "second", "third"])

    def test_down_at_bottom_is_noop(self) -> None:
        """'down' on the last task leaves the column order unchanged."""
        self.svc.reorder_task(Path("alpha/todo/third"), "down")
        self.assertEqual(self._slugs(), ["first", "second", "third"])

    def test_returns_the_reordered_task(self) -> None:
        """reorder_task returns the task that was moved."""
        result = self.svc.reorder_task(Path("alpha/todo/second"), "up")
        self.assertEqual(result.slug, "second")
        self.assertEqual(result.board, "alpha")
        self.assertEqual(result.column, "todo")


if __name__ == "__main__":
    unittest.main()
