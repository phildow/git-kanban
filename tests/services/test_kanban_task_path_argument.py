"""Tests that KanbanService task methods accept both str and Path for `path`."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.base import TaskAlreadyExists, TaskNotFound
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
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
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

    def test_reorder_task_accepts_path(self) -> None:
        """reorder_task changes position for the correct task when path is a Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="first"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="second"))

        self.svc.reorder_task(Path("alpha/todo/second"), "up")
        self.assertEqual([t.slug for t in self.svc.get_tasks("alpha/todo")], ["second", "first"])

        self.svc.reorder_task(Path("alpha/todo/second"), "down")
        self.assertEqual([t.slug for t in self.svc.get_tasks("alpha/todo")], ["first", "second"])

    def test_assign_task_accepts_path(self) -> None:
        """assign_task assigns the correct task when path is a Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_str = self.svc.assign_task(Path("alpha/todo/fix-login"), "alice")
        via_path = self.svc.assign_task(Path("alpha/todo/write-docs"), "bob")

        self.assertEqual(via_str.assigned_to, "alice")
        self.assertEqual(via_path.assigned_to, "bob")

    def test_delete_task_accepts_path(self) -> None:
        """delete_task removes the correct task when path is a Path."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        self.svc.delete_task(Path("alpha/todo/fix-login"))
        self.svc.delete_task(Path("alpha/todo/write-docs"))

        self.assertEqual(self.svc.get_tasks("alpha/todo"), [])

    @patch("kanban.utils.interaction.subprocess.run")
    def test_edit_task_accepts_path(self, mock_run: MagicMock) -> None:
        """edit_task resolves the correct task when path is a Path (editor is a no-op)."""
        mock_run.return_value = None
        created_via_path_1 = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
        created_via_path = self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs"))

        via_path_1 = self.svc.edit_task(Path("alpha/todo/fix-login"))
        via_path = self.svc.edit_task(Path("alpha/todo/write-docs"))

        self.assertEqual(via_path_1.id, created_via_path_1.id)
        self.assertEqual(via_path.id, created_via_path.id)


class TestKanbanServiceBareTaskSlug(unittest.TestCase):
    """Task-scoped methods resolve a bare Slug against the active board.

    The REPL addresses a task by its slug alone; the service locates the column
    that contains it, so callers do not need to supply board/column segments.
    """

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "done", slug="done")
        # Make "alpha" the active board so bare slugs resolve against it.
        self.svc.working_board = Slug("alpha")

    def test_get_task_resolves_bare_slug_in_first_column(self) -> None:
        """A bare slug is matched to its containing column, not assumed to be one."""
        created = self.svc.create_task("/alpha/todo", TaskCreateParams(title="fix-login"))

        resolved = self.svc.get_task(Slug("fix-login"))

        self.assertEqual(resolved.id, created.id)
        self.assertEqual(resolved.column, "todo")

    def test_get_task_resolves_bare_slug_in_other_column(self) -> None:
        """The column is discovered by search, so any column in the board is reachable."""
        created = self.svc.create_task("/alpha/done", TaskCreateParams(title="ship-it"))

        resolved = self.svc.get_task(Slug("ship-it"))

        self.assertEqual(resolved.id, created.id)
        self.assertEqual(resolved.column, "done")

    def test_move_task_accepts_bare_slug(self) -> None:
        """move_task locates the task's column first, then relocates it."""
        self.svc.create_task("/alpha/todo", TaskCreateParams(title="fix-login"))

        moved = self.svc.move_task(Slug("fix-login"), Slug("done"))

        self.assertEqual(moved.column, "done")

    def test_assign_task_accepts_bare_slug(self) -> None:
        """assign_task resolves a bare slug and assigns the correct task."""
        self.svc.create_task("/alpha/done", TaskCreateParams(title="ship-it"))

        assigned = self.svc.assign_task(Slug("ship-it"), "alice")

        self.assertEqual(assigned.assigned_to, "alice")

    def test_delete_task_accepts_bare_slug(self) -> None:
        """delete_task resolves a bare slug and removes the correct task."""
        self.svc.create_task("/alpha/todo", TaskCreateParams(title="fix-login"))

        self.svc.delete_task(Slug("fix-login"))

        self.assertEqual(self.svc.get_tasks("/alpha/todo"), [])

    def test_bare_slug_not_found_raises_task_not_found(self) -> None:
        """A slug matching no task in the board raises TaskNotFound."""
        with self.assertRaises(TaskNotFound):
            self.svc.get_task(Slug("does-not-exist"))

    def test_bare_slug_without_active_board_raises(self) -> None:
        """With no active board there is nothing to search, so resolution fails."""
        self.svc.working_board = None
        with self.assertRaises(ValueError):
            self.svc.get_task(Slug("fix-login"))

    def test_create_task_rejects_duplicate_slug_in_other_column(self) -> None:
        """Task slugs are unique board-wide, so a collision in any column is rejected."""
        self.svc.create_task("/alpha/todo", TaskCreateParams(title="Fix login"))

        with self.assertRaises(TaskAlreadyExists):
            self.svc.create_task("/alpha/done", TaskCreateParams(title="Fix login"))


if __name__ == "__main__":
    unittest.main()
