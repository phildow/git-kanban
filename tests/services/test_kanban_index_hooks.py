"""Tests that KanbanService task mutations call IndexService hooks."""

from __future__ import annotations

import sys
import tempfile
import unittest

from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock

from models import UserContext
from services.git import GitService
from services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from storage.memory import InMemoryRepository


class TestKanbanServiceTaskIndexHooks(unittest.TestCase):
    """Verifies index update/delete hooks for task-changing operations."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.index_service = MagicMock()
        self.svc = KanbanService(
            repository=self.repo,
            index_service=self.index_service,
            git_service=GitService(),
        )

        self.repo.create_board("alpha")
        self.repo.create_column("alpha", "todo")
        self.repo.create_column("alpha", "done")

    def test_create_task_calls_index_update(self) -> None:
        """Creating a task invokes index_service.update_task with the created task."""
        created = self.svc.create_task("alpha/todo/t1", TaskCreateParams())

        self.index_service.update_task.assert_called_once()
        self.assertEqual(self.index_service.update_task.call_args.args[0].id, created.id)

    def test_update_task_calls_index_update(self) -> None:
        """Updating a task invokes index_service.update_task with the updated task."""
        self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        self.index_service.reset_mock()

        updated = self.svc.update_task("alpha/todo/t1", TaskUpdateParams(assigned_to="alice"))

        self.index_service.update_task.assert_called_once()
        self.assertEqual(self.index_service.update_task.call_args.args[0].id, updated.id)

    def test_assign_task_calls_index_update(self) -> None:
        """Assigning a task invokes index_service.update_task with the updated task."""
        self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        self.index_service.reset_mock()

        updated = self.svc.assign_task("alpha/todo/t1", "alice")

        self.index_service.update_task.assert_called_once()
        self.assertEqual(self.index_service.update_task.call_args.args[0].id, updated.id)

    def test_move_task_calls_index_update(self) -> None:
        """Moving a task invokes index_service.update_task with the moved task."""
        self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        self.index_service.reset_mock()

        moved = self.svc.move_task("alpha/todo/t1", "done")

        self.index_service.update_task.assert_called_once()
        self.assertEqual(self.index_service.update_task.call_args.args[0].id, moved.id)

    def test_delete_task_calls_index_delete(self) -> None:
        """Deleting a task invokes index_service.delete_task with the deleted task."""
        created = self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.delete_task("alpha/todo/t1")

        self.index_service.delete_task.assert_called_once()
        self.assertEqual(self.index_service.delete_task.call_args.args[0].id, created.id)

    def test_delete_column_calls_index_delete_for_each_task(self) -> None:
        """Deleting a column invokes index_service.delete_task once per task it contained."""
        t1 = self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        t2 = self.svc.create_task("alpha/todo/t2", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.delete_column("alpha/todo")

        self.assertEqual(self.index_service.delete_task.call_count, 2)
        deleted_ids = {c.args[0].id for c in self.index_service.delete_task.call_args_list}
        self.assertEqual(deleted_ids, {t1.id, t2.id})

    def test_delete_column_with_no_tasks_calls_no_index_delete(self) -> None:
        """Deleting an empty column does not invoke index_service.delete_task."""
        self.svc.delete_column("alpha/todo")

        self.index_service.delete_task.assert_not_called()

    def test_delete_board_calls_index_delete_for_each_task(self) -> None:
        """Deleting a board invokes index_service.delete_task once per task across all columns."""
        t1 = self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        t2 = self.svc.create_task("alpha/todo/t2", TaskCreateParams())
        t3 = self.svc.create_task("alpha/done/t3", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.delete_board("alpha")

        self.assertEqual(self.index_service.delete_task.call_count, 3)
        deleted_ids = {c.args[0].id for c in self.index_service.delete_task.call_args_list}
        self.assertEqual(deleted_ids, {t1.id, t2.id, t3.id})

    def test_delete_board_with_no_tasks_calls_no_index_delete(self) -> None:
        """Deleting a board with no tasks does not invoke index_service.delete_task."""
        self.svc.delete_board("alpha")

        self.index_service.delete_task.assert_not_called()

    def test_rename_column_calls_index_update_for_each_task(self) -> None:
        """Renaming a column invokes index_service.update_task once per task in that column."""
        t1 = self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        t2 = self.svc.create_task("alpha/todo/t2", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.rename_column("alpha/todo", "doing")

        self.assertEqual(self.index_service.update_task.call_count, 2)
        updated_ids = {c.args[0].id for c in self.index_service.update_task.call_args_list}
        self.assertEqual(updated_ids, {t1.id, t2.id})

    def test_rename_column_index_update_reflects_new_column_name(self) -> None:
        """Tasks passed to index_service.update_task after rename carry the new column name."""
        self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.rename_column("alpha/todo", "doing")

        task_arg = self.index_service.update_task.call_args.args[0]
        self.assertEqual(task_arg.column, "doing")

    def test_rename_board_calls_index_update_for_each_task(self) -> None:
        """Renaming a board invokes index_service.update_task once per task in that board."""
        t1 = self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        t2 = self.svc.create_task("alpha/todo/t2", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.rename_board("alpha", "beta")

        self.assertEqual(self.index_service.update_task.call_count, 2)
        updated_ids = {c.args[0].id for c in self.index_service.update_task.call_args_list}
        self.assertEqual(updated_ids, {t1.id, t2.id})

    def test_rename_board_index_update_reflects_new_board_name(self) -> None:
        """Tasks passed to index_service.update_task after rename carry the new board name."""
        self.svc.create_task("alpha/todo/t1", TaskCreateParams())
        self.index_service.reset_mock()

        self.svc.rename_board("alpha", "beta")

        task_arg = self.index_service.update_task.call_args.args[0]
        self.assertEqual(task_arg.board, "beta")


if __name__ == "__main__":
    unittest.main()
