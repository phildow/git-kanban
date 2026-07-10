"""Filesystem bootstrap tests for `KanbanService.initialize_kanban`.

Verifies that the expected directories and files are created on disk when
bootstrapping through KanbanService backed by a real FilesystemRepository.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.seeds import BOOTSTRAP_CONFIG
from kanban.services.kanban import KanbanService
from kanban.index.memory import InMemoryIndex


class TestKanbanInitializeKanbanFilesystem(unittest.TestCase):
    """initialize_kanban writes the expected directory and file layout to disk."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=InMemoryIndex(),
            git_service=MagicMock(),
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    # ------------------------------------------------------------------
    # Storage directories and files
    # ------------------------------------------------------------------

    def test_kanban_dir_exists(self) -> None:
        """.kanban directory is created on disk."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban").is_dir())

    def test_kanban_store_boards_dir_exists(self) -> None:
        """.kanban-store/boards directory is created on disk."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards").is_dir())

    # ------------------------------------------------------------------
    # Board directory
    # ------------------------------------------------------------------

    def test_main_board_directory_exists(self) -> None:
        """A directory for the main board is created under .kanban-store/boards."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "main").is_dir())

    def test_main_board_metadata_file_exists(self) -> None:
        """The main board .metadata file is created on disk."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "main" / ".metadata").is_file())

    def test_main_board_metadata_has_name(self) -> None:
        """The board name is written to fields.name in the board .metadata file."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        name = self.repo.get_board_metadata("main", "fields.name")
        self.assertEqual(name, "Main")

    def test_main_board_metadata_has_slug(self) -> None:
        """The board slug is written to fields.slug in the board .metadata file."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        slug = self.repo.get_board_metadata("main", "fields.slug")
        self.assertEqual(slug, "main")

    # ------------------------------------------------------------------
    # Column directories
    # ------------------------------------------------------------------

    def test_todo_column_directory_exists(self) -> None:
        """todo column directory is created under the main board."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "main" / "todo").is_dir())

    def test_in_progress_column_directory_exists(self) -> None:
        """in-progress column directory is created under the main board."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "main" / "in-progress").is_dir())

    def test_in_review_column_directory_exists(self) -> None:
        """in-review column directory is created under the main board."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "main" / "in-review").is_dir())

    def test_done_column_directory_exists(self) -> None:
        """done column directory is created under the main board."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "main" / "done").is_dir())

    # ------------------------------------------------------------------
    # Task files
    # ------------------------------------------------------------------

    def test_seed_task_file_exists_in_todo(self) -> None:
        """Seed task file list-your-boards-and-tasks.md is created in todo."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        path = self.root / ".kanban-store" / "boards" / "main" / "todo" / "list-your-boards-and-tasks.md"
        self.assertTrue(path.is_file())

    def test_seed_task_file_exists_in_in_progress(self) -> None:
        """Seed task file update-a-task-with-details.md is created in in-progress."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        path = self.root / ".kanban-store" / "boards" / "main" / "in-progress" / "update-a-task-with-details.md"
        self.assertTrue(path.is_file())

    def test_seed_task_file_exists_in_done(self) -> None:
        """Seed task file go-for-a-bike-ride.md is created in done."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        path = self.root / ".kanban-store" / "boards" / "main" / "done" / "go-for-a-bike-ride.md"
        self.assertTrue(path.is_file())

    # ------------------------------------------------------------------
    # User context
    # ------------------------------------------------------------------

    def test_user_context_board_is_set(self) -> None:
        """User context board is set to main after bootstrap."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertEqual(self.svc.user_context.board, "main")

    def test_user_context_column_is_set(self) -> None:
        """User context column is set to todo after bootstrap."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertEqual(self.svc.user_context.column, "todo")

    def test_userdata_file_records_board(self) -> None:
        """User context board is persisted to .kanban/userdata."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertEqual(self.repo.get_userdata("user-context.board"), "main")

    def test_userdata_file_records_column(self) -> None:
        """User context column is persisted to .kanban/userdata."""
        self.svc.initialize_kanban(config=BOOTSTRAP_CONFIG)
        self.assertEqual(self.repo.get_userdata("user-context.column"), "todo")


class TestKanbanInitializeKanbanFilesystemCustomBoard(unittest.TestCase):
    """initialize_kanban with a board whose display name contains spaces."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=InMemoryIndex(),
            git_service=MagicMock(),
        )
        self.config = {
            "usercontext": {
                "board": "my-project", 
                "column": "todo"
            },
            "boards": [
                {
                    "name": "My Project",
                    "slug": "my-project",
                    "columns": [
                        {
                            "name": "Todo", 
                            "slug": "todo", 
                            "tasks": [
                                {
                                    "title": "first task", 
                                    "slug": "first-task"
                                    },
                            ]
                        },
                        {
                            "name": "Done", 
                            "slug": "done", 
                            "tasks": []
                        },
                    ],
                }
            ],
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_board_directory_uses_slug(self) -> None:
        """Board directory is named after the slug, not the display name."""
        self.svc.initialize_kanban(config=self.config)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "my-project").is_dir())

    def test_board_directory_not_named_with_spaces(self) -> None:
        """No directory is created with the raw display name (spaces preserved)."""
        self.svc.initialize_kanban(config=self.config)
        self.assertFalse((self.root / ".kanban-store" / "boards" / "My Project").is_dir())

    def test_column_directory_uses_slug_path(self) -> None:
        """Column is created inside the slug-named board directory."""
        self.svc.initialize_kanban(config=self.config)
        self.assertTrue((self.root / ".kanban-store" / "boards" / "my-project" / "todo").is_dir())

    def test_task_file_uses_slug_path(self) -> None:
        """Task file is created inside the slug-named board/column path."""
        self.svc.initialize_kanban(config=self.config)
        path = self.root / ".kanban-store" / "boards" / "my-project" / "todo" / "first-task.md"
        self.assertTrue(path.is_file())

    def test_board_metadata_has_display_name(self) -> None:
        """fields.name in .metadata stores the display name, not the slug."""
        self.svc.initialize_kanban(config=self.config)
        name = self.repo.get_board_metadata("my-project", "fields.name")
        self.assertEqual(name, "My Project")

    def test_board_metadata_has_slug(self) -> None:
        """fields.slug in .metadata stores the kebab-case slug."""
        self.svc.initialize_kanban(config=self.config)
        slug = self.repo.get_board_metadata("my-project", "fields.slug")
        self.assertEqual(slug, "my-project")


if __name__ == "__main__":
    unittest.main()
