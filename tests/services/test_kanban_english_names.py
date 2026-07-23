"""Tests for KanbanService with multi-word English display names.

These tests exercise the name/slug distinction end-to-end: boards, columns,
and tasks are created and updated with display names that include spaces and
mixed case.  Each test verifies that the display name is preserved exactly
and that the derived slug is the correct kebab-case form.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceEnglishNames(unittest.TestCase):
    """Name/slug round-trip tests using multi-word display names."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
        )

    # ── Boards ────────────────────────────────────────────────────────────────

    def test_create_board_preserves_display_name(self) -> None:
        """A multi-word board name is stored exactly as given."""
        board = self.svc.create_board("My Project")
        self.assertEqual(board.name, "My Project")

    def test_create_board_derives_slug(self) -> None:
        """A multi-word board name produces a kebab-case slug."""
        board = self.svc.create_board("My Project")
        self.assertEqual(board.slug, "my-project")

    def test_create_board_default_columns_have_display_names(self) -> None:
        """Default columns carry their full display names, not slugs."""
        self.svc.create_board("My Project")
        names = [c.name for c in self.repo.get_columns("my-project")]
        self.assertEqual(names, ["To Do", "In Progress", "In Review", "Done"])

    def test_create_board_default_columns_have_slugs(self) -> None:
        """Default column slugs are the kebab-case form of their display names."""
        self.svc.create_board("My Project")
        slugs = [c.slug for c in self.repo.get_columns("my-project")]
        self.assertEqual(slugs, ["todo", "in-progress", "in-review", "done"])

    def test_rename_board_preserves_new_display_name(self) -> None:
        """Renaming a board to a multi-word name stores it exactly."""
        self.svc.create_board("My Project", columns=[])
        board = self.svc.rename_board(Path("my-project"), "My Renamed Project")
        self.assertEqual(board.name, "My Renamed Project")

    def test_rename_board_updates_slug(self) -> None:
        """Renaming a board updates the slug to match the new display name."""
        self.svc.create_board("My Project", columns=[])
        board = self.svc.rename_board(Path("my-project"), "My Renamed Project")
        self.assertEqual(board.slug, "my-renamed-project")

    # ── Columns ───────────────────────────────────────────────────────────────

    def test_create_column_preserves_display_name(self) -> None:
        """A multi-word column name is stored exactly as given."""
        self.svc.create_board("My Project", columns=[])
        column = self.svc.create_column(Path("my-project"), "In Progress")
        self.assertEqual(column.name, "In Progress")

    def test_create_column_derives_slug(self) -> None:
        """A multi-word column name produces a kebab-case slug."""
        self.svc.create_board("My Project", columns=[])
        column = self.svc.create_column(Path("my-project"), "In Progress")
        self.assertEqual(column.slug, "in-progress")

    def test_rename_column_preserves_new_display_name(self) -> None:
        """Renaming a column to a multi-word name stores it exactly."""
        self.svc.create_board("My Project", columns=[("Backlog", "backlog")])
        column = self.svc.rename_column(Path("my-project/backlog"), "In Progress")
        self.assertEqual(column.name, "In Progress")

    def test_rename_column_updates_slug(self) -> None:
        """Renaming a column updates the slug to match the new display name."""
        self.svc.create_board("My Project", columns=[("Backlog", "backlog")])
        column = self.svc.rename_column(Path("my-project/backlog"), "In Progress")
        self.assertEqual(column.slug, "in-progress")

    # ── Tasks ─────────────────────────────────────────────────────────────────

    def test_create_task_preserves_title(self) -> None:
        """A multi-word task title is stored exactly as given."""
        self.svc.create_board("My Project", columns=[("To Do", "todo")])
        task = self.svc.create_task("my-project/todo", TaskCreateParams(title="Fix Login Bug"))
        self.assertEqual(task.title, "Fix Login Bug")

    def test_create_task_derives_slug(self) -> None:
        """A multi-word task title produces a kebab-case slug."""
        self.svc.create_board("My Project", columns=[("To Do", "todo")])
        task = self.svc.create_task("my-project/todo", TaskCreateParams(title="Fix Login Bug"))
        self.assertEqual(task.slug, "fix-login-bug")

    def test_task_is_retrievable_by_slug(self) -> None:
        """A task created with a display name is retrievable via its slug path."""
        self.svc.create_board("My Project", columns=[("To Do", "todo")])
        self.svc.create_task("my-project/todo", TaskCreateParams(title="Fix Login Bug"))
        task = self.svc.get_task(Path("my-project/todo/fix-login-bug"))
        self.assertEqual(task.title, "Fix Login Bug")

    def test_update_task_title_preserves_new_display_name(self) -> None:
        """Updating a task title stores the new multi-word name exactly."""
        self.svc.create_board("My Project", columns=[("To Do", "todo")])
        self.svc.create_task("my-project/todo", TaskCreateParams(title="Fix Login Bug"))
        updated = self.svc.update_task(
            Path("my-project/todo/fix-login-bug"),
            TaskUpdateParams(title="Fix Registration Bug"),
        )
        self.assertEqual(updated.title, "Fix Registration Bug")

    def test_update_task_title_updates_slug(self) -> None:
        """Updating a task title changes the slug to match the new name."""
        self.svc.create_board("My Project", columns=[("To Do", "todo")])
        self.svc.create_task("my-project/todo", TaskCreateParams(title="Fix Login Bug"))
        updated = self.svc.update_task(
            Path("my-project/todo/fix-login-bug"),
            TaskUpdateParams(title="Fix Registration Bug"),
        )
        self.assertEqual(updated.slug, "fix-registration-bug")


if __name__ == "__main__":
    unittest.main()
