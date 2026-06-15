"""Tests that KanbanService task mutations call IndexService hooks."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KANBAN_SRC = PROJECT_ROOT / "kanban"
if str(KANBAN_SRC) not in sys.path:
    sys.path.insert(0, str(KANBAN_SRC))

from services.git_service import GitService
from services.kanban_service import KanbanService, TaskCreateParams
from storage.memory_repository import InMemoryRepository


class TestKanbanServiceTaskIndexHooks(unittest.TestCase):
    """Verifies index update/delete hooks for task-changing operations."""

    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.index_service = MagicMock()
        self.svc = KanbanService(
            repository=self.repo,
            index_service=self.index_service,
            git_service=GitService(),
        )

        self.repo.create_board("alpha")
        self.repo.create_column("alpha", "todo")

    def test_create_task_calls_index_update(self):
        """Creating a task should invoke `index_service.update()` with created task."""
        created = self.svc.create_task("alpha/todo/t1", TaskCreateParams(title="t1"))

        self.index_service.update.assert_called_once()
        updated_task = self.index_service.update.call_args.args[0]
        self.assertEqual(updated_task.id, created.id)

    def test_delete_task_calls_index_delete(self):
        """Deleting a task should invoke `index_service.delete()` with deleted task."""
        self.svc.create_task("alpha/todo/t1", TaskCreateParams(title="t1"))

        self.svc.delete_task("alpha/todo/t1")

        self.index_service.delete.assert_called_once()


if __name__ == "__main__":
    unittest.main()
