"""Bootstrap tests for `KanbanService.init()`.

These tests document initialization semantics for in-memory bootstrapping.
"""

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from uuid import uuid4

from kanban.storage.seeds import BOOTSTRAP_CONFIG
from kanban.services.kanban import KanbanService
from kanban.services.git import GitService
from kanban.index.memory import InMemoryIndexService
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceInitKanban(unittest.TestCase):
    """Tests for one-time repository bootstrap behavior."""

    def test_init_creates_main_board_and_marks_initialized(self):
        """First init creates main board, default columns, context, and init flag."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=InMemoryIndexService(repository=repo),
            git_service=GitService(),
        )

        result = svc.initialize_kanban(Path("."), config=BOOTSTRAP_CONFIG)

        self.assertTrue(result)
        self.assertTrue(repo.board_exists("main"))
        self.assertEqual(
            [c.name for c in repo.get_columns("main")],
            ["To Do", "In Progress", "In Review", "Done"],
        )
        self.assertEqual(
            [c.slug for c in repo.get_columns("main")],
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
            index_service=InMemoryIndexService(repository=repo),
            git_service=GitService(),
        )

        svc.initialize_kanban(Path("."), config=BOOTSTRAP_CONFIG)
        with self.assertRaises(ValueError):
            svc.initialize_kanban(Path("."), config=BOOTSTRAP_CONFIG)

    def test_init_seeds_tasks_from_default_seeds(self):
        """initialize_kanban creates tasks from BOOTSTRAP_SEEDS in the main board."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=InMemoryIndexService(repository=repo),
            git_service=GitService(),
        )

        svc.initialize_kanban(Path("."), config=BOOTSTRAP_CONFIG)

        tasks = repo.get_tasks(board="main")
        titles = {t.title for t in tasks}
        self.assertIn("List your boards and tasks", titles)
        self.assertIn("Create a new task", titles)
        self.assertIn("Move a task to another column", titles)
        self.assertIn("Update a task with details", titles)
        self.assertIn("Go for a bike ride", titles)

    def test_init_seeds_tasks_from_custom_config(self):
        """initialize_kanban accepts a custom BootstrapConfig instead of the default."""
        from kanban.storage.seeds import BootstrapConfig
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=InMemoryIndexService(repository=repo),
            git_service=GitService(),
        )
        custom: BootstrapConfig = {
            "boards": [
                {
                    "name": "work",
                    "slug": "work",
                    "columns": [
                        {"name": "Backlog", "slug": "backlog", "tasks": [
                            {"title": "custom task", "slug": "custom-task"},
                        ]},
                        {"name": "Doing", "slug": "doing", "tasks": []},
                        {"name": "Done", "slug": "done", "tasks": []},
                    ],
                }
            ],
        }

        svc.initialize_kanban(Path("."), config=custom)

        self.assertTrue(repo.board_exists("work"))
        self.assertEqual([c.name for c in repo.get_columns("work")], ["Backlog", "Doing", "Done"])
        self.assertEqual([c.slug for c in repo.get_columns("work")], ["backlog", "doing", "done"])
        titles = {t.title for t in repo.get_tasks(board="work")}
        self.assertIn("custom task", titles)
        self.assertNotIn("list your boards and tasks", titles)


if __name__ == "__main__":
    unittest.main()
