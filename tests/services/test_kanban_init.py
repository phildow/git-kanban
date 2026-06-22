"""Bootstrap tests for `KanbanService.init()`.

These tests document initialization semantics for in-memory bootstrapping.
"""

from __future__ import annotations

import sys
import tempfile
import unittest

from pathlib import Path
from uuid import uuid4

from models import UserContext
from services.kanban import KanbanService
from services.git import GitService
from services.index import IndexService
from storage.memory import InMemoryRepository


class TestKanbanServiceInitKanban(unittest.TestCase):
    """Tests for one-time repository bootstrap behavior."""

    def test_init_creates_main_board_and_marks_initialized(self):
        """First init creates main board, default columns, context, and init flag."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
        )

        result = svc.init_kanban(Path("."))

        self.assertTrue(result)
        self.assertTrue(repo.board_exists("main"))
        self.assertEqual(
            [c.name for c in repo.get_columns("main")],
            ["todo", "in-progress", "in-review", "done"],
        )
        self.assertEqual(
            [c.position for c in repo.get_columns("main")],
            [0, 1, 2, 3],
        )

        self.assertEqual(svc.user_context.board, "main")
        self.assertEqual(svc.user_context.column, "todo")

    def test_init_raises_when_called_twice(self):
        """Second init call raises because repository is already initialized."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
        )

        svc.init_kanban(Path("."))
        with self.assertRaises(ValueError):
            svc.init_kanban(Path("."))

    def test_init_seeds_tasks_from_default_seeds(self):
        """init_kanban creates tasks from BOOTSTRAP_SEEDS in the main board."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
        )

        svc.init_kanban(Path("."))

        tasks = repo.get_tasks(board="main")
        titles = {t.title for t in tasks}
        self.assertIn("list your boards and tasks", titles)
        self.assertIn("create a new task", titles)
        self.assertIn("move a task to another column", titles)
        self.assertIn("update a task with details", titles)
        self.assertIn("go for a bike ride", titles)

    def test_init_seeds_tasks_from_custom_config(self):
        """init_kanban accepts a custom BootstrapConfig instead of the default."""
        from storage.seeds import BootstrapConfig
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=IndexService(repository=repo),
            git_service=GitService(),
        )
        custom: BootstrapConfig = {
            "boards": [
                {
                    "name": "work",
                    "columns": ["backlog", "doing", "done"],
                    "tasks": [
                        {"title": "custom task", "slug": "custom-task", "column": "backlog"},
                    ],
                }
            ],
        }

        svc.init_kanban(Path("."), config=custom)

        self.assertTrue(repo.board_exists("work"))
        self.assertEqual([c.name for c in repo.get_columns("work")], ["backlog", "doing", "done"])
        titles = {t.title for t in repo.get_tasks(board="work")}
        self.assertIn("custom task", titles)
        self.assertNotIn("list your boards and tasks", titles)


if __name__ == "__main__":
    unittest.main()
