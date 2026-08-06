"""Tests for KanbanService column read methods: get_columns, get_column, reorder_column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Column
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService
from kanban.storage.base import BoardNotFound, ColumnAlreadyExists, ColumnNotFound
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceGetColumns(unittest.TestCase):
    """get_columns returns the columns of a board, honoring active-board context."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "done", slug="done")

    def test_get_columns_by_slug_returns_all_columns(self) -> None:
        """get_columns returns every column for the given board slug."""
        columns = self.svc.get_columns("alpha")
        self.assertEqual([c.slug for c in columns], ["todo", "done"])

    def test_get_columns_by_path_returns_all_columns(self) -> None:
        """get_columns accepts a Path with a leading slash."""
        columns = self.svc.get_columns(Path("/alpha"))
        self.assertEqual([c.slug for c in columns], ["todo", "done"])

    def test_get_columns_falls_back_to_active_board(self) -> None:
        """get_columns uses the working board when no argument is given."""
        self.svc.working_board = "alpha"
        columns = self.svc.get_columns()
        self.assertEqual([c.slug for c in columns], ["todo", "done"])

    def test_get_columns_raises_without_any_board(self) -> None:
        """get_columns raises when no board is specified and no active board is set."""
        with self.assertRaises(ValueError):
            self.svc.get_columns()

    def test_get_columns_raises_for_missing_board(self) -> None:
        """get_columns raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.get_columns("missing")


class TestKanbanServiceGetColumn(unittest.TestCase):
    """get_column resolves a single column by board/column path."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")

    def test_get_column_returns_column_instance(self) -> None:
        """get_column returns a Column dataclass for a valid board/column path."""
        column = self.svc.get_column(Path("alpha/todo"))

        self.assertIsInstance(column, Column)
        self.assertEqual(column.slug, "todo")
        self.assertEqual(column.board, "alpha")

    def test_get_column_raises_for_bare_slug(self) -> None:
        """get_column requires a board and column; a bare column slug is invalid."""
        with self.assertRaises(ValueError):
            self.svc.get_column("todo")

    def test_get_column_raises_when_task_included(self) -> None:
        """get_column rejects a path that includes a task segment."""
        with self.assertRaises(ValueError):
            self.svc.get_column(Path("alpha/todo/some-task"))

    def test_get_column_raises_for_missing_column(self) -> None:
        """get_column raises ColumnNotFound when the column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.svc.get_column(Path("alpha/missing"))


class TestKanbanServiceReorderColumn(unittest.TestCase):
    """reorder_column moves a column to a new position and returns the new order."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "doing", slug="doing")
        self.repo.create_column("alpha", "done", slug="done")

    def test_reorder_column_moves_to_new_position(self) -> None:
        """reorder_column moves the target column to the given position."""
        columns = self.svc.reorder_column(Path("alpha/done"), 0)
        self.assertEqual([c.slug for c in columns], ["done", "todo", "doing"])

    def test_reorder_column_returns_full_column_list(self) -> None:
        """reorder_column returns the updated ordering of all columns."""
        columns = self.svc.reorder_column(Path("alpha/todo"), 2)
        self.assertEqual(len(columns), 3)

    def test_reorder_column_raises_for_bare_slug(self) -> None:
        """reorder_column requires a board/column path, not a bare column slug."""
        with self.assertRaises(ValueError):
            self.svc.reorder_column("todo", 0)

    def test_reorder_column_raises_for_missing_column(self) -> None:
        """reorder_column raises ColumnNotFound when the column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.svc.reorder_column(Path("alpha/missing"), 0)


class TestKanbanServiceCreateColumn(unittest.TestCase):
    """create_column adds a new column, honoring the active-board context."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )
        self.repo.create_board("alpha", slug="alpha")

    def test_create_column_by_path_returns_column(self) -> None:
        """create_column returns the newly created Column with the given name."""
        column = self.svc.create_column(Path("alpha"), "todo")
        self.assertIsInstance(column, Column)
        self.assertEqual(column.name, "todo")
        self.assertEqual(column.board, "alpha")

    def test_create_column_derives_slug_from_name(self) -> None:
        """create_column slugs the name to produce the column's slug."""
        column = self.svc.create_column(Path("alpha"), "In Progress")
        self.assertEqual(column.slug, "in-progress")

    def test_create_column_persists_to_repository(self) -> None:
        """The new column is retrievable from the repository afterwards."""
        self.svc.create_column(Path("alpha"), "todo")
        slugs = [c.slug for c in self.repo.get_columns("alpha")]
        self.assertIn("todo", slugs)

    def test_create_column_uses_active_board_when_path_is_none(self) -> None:
        """create_column with path=None adds the column to the active board."""
        self.svc.working_board = "alpha"
        column = self.svc.create_column(None, "todo")
        self.assertEqual(column.board, "alpha")

    def test_create_column_raises_without_path_or_active_board(self) -> None:
        """create_column raises when neither a path nor an active board is provided."""
        with self.assertRaises(ValueError):
            self.svc.create_column(None, "todo")

    def test_create_column_raises_for_missing_board(self) -> None:
        """create_column raises BoardNotFound when the target board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.create_column(Path("missing"), "todo")

    def test_create_column_raises_when_name_already_exists(self) -> None:
        """create_column raises ColumnAlreadyExists when the name is taken."""
        self.svc.create_column(Path("alpha"), "todo")

        with self.assertRaises(ColumnAlreadyExists):
            self.svc.create_column(Path("alpha"), "todo")


class TestKanbanServiceRenameColumn(unittest.TestCase):
    """rename_column updates the column's name and slug."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "done", slug="done")

    def test_rename_column_updates_name(self) -> None:
        """rename_column returns a Column with the new display name."""
        column = self.svc.rename_column(Path("alpha/todo"), "Doing")
        self.assertEqual(column.name, "Doing")

    def test_rename_column_updates_slug(self) -> None:
        """rename_column slugs the new name and updates the column's slug."""
        column = self.svc.rename_column(Path("alpha/todo"), "In Progress")
        self.assertEqual(column.slug, "in-progress")

    def test_rename_column_persists_new_slug_in_repository(self) -> None:
        """After rename the column is retrievable under its new slug."""
        self.svc.rename_column(Path("alpha/todo"), "In Progress")

        slugs = [c.slug for c in self.repo.get_columns("alpha")]
        self.assertIn("in-progress", slugs)
        self.assertNotIn("todo", slugs)

    def test_rename_column_raises_for_bare_slug(self) -> None:
        """rename_column requires a board/column path, not a bare column slug."""
        with self.assertRaises(ValueError):
            self.svc.rename_column("todo", "Doing")

    def test_rename_column_raises_for_missing_board(self) -> None:
        """rename_column raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.rename_column(Path("missing/todo"), "Doing")

    def test_rename_column_raises_for_missing_column(self) -> None:
        """rename_column raises ColumnNotFound when the column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.svc.rename_column(Path("alpha/missing"), "Doing")

    def test_rename_column_raises_when_new_name_already_exists(self) -> None:
        """rename_column raises ColumnAlreadyExists when the new name is taken."""
        with self.assertRaises(ColumnAlreadyExists):
            self.svc.rename_column(Path("alpha/todo"), "done")


class TestKanbanServiceDeleteColumn(unittest.TestCase):
    """delete_column removes a column from its board."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_column("alpha", "done", slug="done")

    def test_delete_column_returns_deleted_column(self) -> None:
        """delete_column returns the Column that was removed."""
        deleted = self.svc.delete_column(Path("alpha/done"))

        self.assertIsInstance(deleted, Column)
        self.assertEqual(deleted.slug, "done")

    def test_delete_column_removes_it_from_repository(self) -> None:
        """After delete_column the column is no longer listed for the board."""
        self.svc.delete_column(Path("alpha/done"))

        slugs = [c.slug for c in self.repo.get_columns("alpha")]
        self.assertNotIn("done", slugs)

    def test_delete_column_raises_for_bare_slug(self) -> None:
        """delete_column requires a board/column path, not a bare column slug."""
        with self.assertRaises(ValueError):
            self.svc.delete_column("done")

    def test_delete_column_raises_for_missing_board(self) -> None:
        """delete_column raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.delete_column(Path("missing/todo"))

    def test_delete_column_raises_for_missing_column(self) -> None:
        """delete_column raises ColumnNotFound when the column does not exist."""
        with self.assertRaises(ColumnNotFound):
            self.svc.delete_column(Path("alpha/missing"))


if __name__ == "__main__":
    unittest.main()
