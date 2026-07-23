"""Tests that KanbanService task methods accept both str and Path for `path`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceTaskPathArgument(unittest.TestCase):
    """Task-scoped KanbanService methods behave identically for str and Path paths."""

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
        self.repo.create_column("alpha", "done", slug="done")

    def test_create_task_accepts_str_and_path(self) -> None:
        """create_task resolves an equivalent location whether path is str or Path."""
        via_str = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        via_path = self.svc.create_task(Path("alpha/todo"), TaskCreateParams(title="write-docs"))

        self.assertEqual(via_str.slug, "fix-login")
        self.assertEqual(via_path.slug, "write-docs")
        self.assertEqual(via_path.board, "alpha")
        self.assertEqual(via_path.column, "todo")

    def test_get_task_accepts_path(self) -> None:
        """get_task resolves the same task when given a Path."""
        created = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

        via_path = self.svc.get_task(Path("alpha/todo/fix-login"))

        self.assertEqual(via_path.id, created.id)

    def test_get_columns_accepts_slug_and_path(self) -> None:
        """get_columns resolves the same board whether board is slug or Path."""
        via_slug = self.svc.get_columns("alpha")
        via_path = self.svc.get_columns(Path("/alpha"))

        self.assertEqual([c.slug for c in via_slug], ["todo", "done"])
        self.assertEqual([c.slug for c in via_path], ["todo", "done"])

    def test_rename_task_accepts_path(self) -> None:
        """rename_task renames the correct task when path is a Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_path_1 = self.svc.rename_task(Path("alpha/todo/fix-login"), "Fix login bug")
        via_path = self.svc.rename_task(Path("alpha/todo/write-docs"), "Write API docs")

        self.assertEqual(via_path_1.title, "Fix login bug")
        self.assertEqual(via_path.title, "Write API docs")

    def test_update_task_accepts_path(self) -> None:
        """update_task applies updates to the correct task when path is a Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_path_1 = self.svc.update_task(Path("alpha/todo/fix-login"), TaskUpdateParams(assigned_to="alice"))
        via_path = self.svc.update_task(Path("alpha/todo/write-docs"), TaskUpdateParams(assigned_to="bob"))

        self.assertEqual(via_path_1.assigned_to, "alice")
        self.assertEqual(via_path.assigned_to, "bob")

    def test_move_task_accepts_path(self) -> None:
        """move_task relocates the correct task when path is a Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_path_1 = self.svc.move_task(Path("alpha/todo/fix-login"), Slug("done"))
        via_path = self.svc.move_task(Path("alpha/todo/write-docs"), Slug("done"))

        self.assertEqual(via_path_1.column, "done")
        self.assertEqual(via_path.column, "done")

    def test_reorder_task_accepts_str_and_path(self) -> None:
        """reorder_task changes position for the correct task whether path is str or Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="first"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="second"))

        self.svc.reorder_task("alpha/todo/second", "up")
        self.assertEqual([t.slug for t in self.svc.get_tasks("alpha/todo")], ["second", "first"])

        self.svc.reorder_task(Path("alpha/todo/second"), "down")
        self.assertEqual([t.slug for t in self.svc.get_tasks("alpha/todo")], ["first", "second"])

    def test_assign_task_accepts_str_and_path(self) -> None:
        """assign_task assigns the correct task whether path is str or Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_str = self.svc.assign_task("alpha/todo/fix-login", "alice")
        via_path = self.svc.assign_task(Path("alpha/todo/write-docs"), "bob")

        self.assertEqual(via_str.assigned_to, "alice")
        self.assertEqual(via_path.assigned_to, "bob")

    def test_delete_task_accepts_str_and_path(self) -> None:
        """delete_task removes the correct task whether path is str or Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        self.svc.delete_task("alpha/todo/fix-login")
        self.svc.delete_task(Path("alpha/todo/write-docs"))

        self.assertEqual(self.svc.get_tasks("alpha/todo"), [])

    @patch("kanban.services.kanban.subprocess.run")
    def test_edit_task_accepts_path(self, mock_run: MagicMock) -> None:
        """edit_task resolves the correct task when path is a Path (editor is a no-op)."""
        mock_run.return_value = None
        created_via_path_1 = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        created_via_path = self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_path_1 = self.svc.edit_task(Path("alpha/todo/fix-login"))
        via_path = self.svc.edit_task(Path("alpha/todo/write-docs"))

        self.assertEqual(via_path_1.id, created_via_path_1.id)
        self.assertEqual(via_path.id, created_via_path.id)


if __name__ == "__main__":
    unittest.main()
