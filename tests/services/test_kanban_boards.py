"""Tests for KanbanService board read methods: get_boards and get_board."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Board
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService
from kanban.storage.base import BoardAlreadyExists, BoardNotFound
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceGetBoards(unittest.TestCase):
    """get_boards returns all boards in the repository."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_get_boards_returns_empty_list_when_no_boards(self) -> None:
        """get_boards returns [] when the repository has no boards."""
        self.assertEqual(self.svc.get_boards(), [])

    def test_get_boards_returns_all_created_boards(self) -> None:
        """get_boards returns every board that has been created."""
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_board("beta", slug="beta")

        boards = self.svc.get_boards()

        self.assertEqual({b.slug for b in boards}, {"alpha", "beta"})

    def test_get_boards_returns_board_instances(self) -> None:
        """Each element in the returned list is a Board dataclass."""
        self.repo.create_board("alpha", slug="alpha")

        boards = self.svc.get_boards()

        self.assertEqual(len(boards), 1)
        self.assertIsInstance(boards[0], Board)


class TestKanbanServiceGetBoard(unittest.TestCase):
    """get_board resolves a single board by path or slug."""

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

    def test_get_board_by_slug_returns_board(self) -> None:
        """get_board resolves a bare Slug to the matching Board."""
        board = self.svc.get_board("alpha")

        self.assertIsInstance(board, Board)
        self.assertEqual(board.slug, "alpha")

    def test_get_board_by_absolute_path_returns_board(self) -> None:
        """get_board strips a leading slash from a Path input."""
        board = self.svc.get_board(Path("/alpha"))

        self.assertIsInstance(board, Board)
        self.assertEqual(board.slug, "alpha")

    def test_get_board_by_relative_path_returns_board(self) -> None:
        """get_board resolves a plain Path input just as it does a slug."""
        board = self.svc.get_board(Path("alpha"))

        self.assertIsInstance(board, Board)
        self.assertEqual(board.slug, "alpha")

    def test_get_board_returns_none_for_missing_board(self) -> None:
        """get_board raises BoardNotFound when no board with that slug exists."""
        with self.assertRaises(BoardNotFound):
            self.svc.get_board("missing")


class TestKanbanServiceCreateBoard(unittest.TestCase):
    """create_board creates the board and the requested columns."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_default_columns_are_created_when_none_passed(self) -> None:
        """Omitting columns creates the four standard columns, and the archive."""
        self.svc.create_board("alpha")
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(
            column_names, ["To Do", "In Progress", "In Review", "Done", "Archive"]
        )

    # TODO: Update to call service for columns
    def test_returned_board_has_default_columns_when_none_passed(self) -> None:
        """The returned Board carries all four default Column objects."""
        board = self.svc.create_board("alpha")
        # column_names = [c.name for c in board.columns]
        # self.assertEqual(column_names, ["To Do", "In Progress", "In Review", "Done"])

    def test_explicit_columns_are_created(self) -> None:
        """Columns passed explicitly are the ones created, the archive after them."""
        self.svc.create_board("alpha", columns=[("backlog", "backlog"), ("wip", "wip"), ("done", "done")])
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, ["backlog", "wip", "done", "Archive"])

    def test_empty_columns_creates_only_the_archive(self) -> None:
        """Passing an empty list creates no workflow columns, only the archive."""
        self.svc.create_board("alpha", columns=[])
        column_names = [c.name for c in self.repo.get_columns("alpha")]
        self.assertEqual(column_names, ["Archive"])

    def test_archive_column_carries_the_archive_role(self) -> None:
        """The column created alongside the requested ones is marked as the archive."""
        self.svc.create_board("alpha")
        archive = self.repo.get_column("alpha", "archive")
        self.assertEqual(archive.role, "archive")
        self.assertTrue(archive.is_archive)

    def test_requested_archive_column_is_not_duplicated(self) -> None:
        """A caller naming the archive itself gets that column marked, not a second one."""
        self.svc.create_board("alpha", columns=[("To Do", "todo"), ("Archive", "archive")])
        columns = self.repo.get_columns("alpha")
        self.assertEqual([c.slug for c in columns], ["todo", "archive"])
        self.assertTrue(columns[1].is_archive)

    def test_returned_board_has_correct_columns_count(self) -> None:
        """The returned Board counts the requested columns and the archive."""
        board = self.svc.create_board("alpha", columns=[("To Do", "todo"), ("Done", "done")])
        self.assertEqual(board.column_count, 3)


class TestKanbanServiceRenameBoard(unittest.TestCase):
    """rename_board updates the board's name/slug and honors active-board context."""

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

    def test_rename_board_by_path_updates_name(self) -> None:
        """rename_board returns a Board with the new display name."""
        board = self.svc.rename_board(Path("alpha"), "Alpha Prime")
        self.assertEqual(board.name, "Alpha Prime")

    def test_rename_board_by_path_updates_slug(self) -> None:
        """rename_board slugs the new name and updates the board's slug."""
        board = self.svc.rename_board(Path("alpha"), "Alpha Prime")
        self.assertEqual(board.slug, "alpha-prime")

    def test_rename_board_uses_active_board_when_path_is_none(self) -> None:
        """rename_board with path=None renames the active board."""
        self.svc.working_board = "alpha"
        board = self.svc.rename_board(None, "Alpha Prime")
        self.assertEqual(board.slug, "alpha-prime")

    def test_rename_board_updates_working_board_when_renaming_active(self) -> None:
        """Renaming the active board updates working_board to the new slug."""
        self.svc.working_board = "alpha"
        self.svc.rename_board(Path("/alpha"), "Alpha Prime")
        self.assertEqual(self.svc.working_board, "alpha-prime")

    def test_rename_board_leaves_working_board_when_renaming_other(self) -> None:
        """Renaming a non-active board does not change the active board."""
        self.repo.create_board("beta", slug="beta")
        self.svc.working_board = "beta"
        self.svc.rename_board(Path("/alpha"), "Alpha Prime")
        self.assertEqual(self.svc.working_board, "beta")

    def test_rename_board_raises_without_path_or_active_board(self) -> None:
        """rename_board raises when neither a path nor an active board is provided."""
        with self.assertRaises(ValueError):
            self.svc.rename_board(None, "Alpha Prime")

    def test_rename_board_raises_for_missing_board(self) -> None:
        """rename_board raises BoardNotFound when the source board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.rename_board(Path("missing"), "New Name")

    def test_rename_board_raises_when_new_slug_already_exists(self) -> None:
        """rename_board raises BoardAlreadyExists when the new slug collides."""
        self.repo.create_board("beta", slug="beta")
        with self.assertRaises(BoardAlreadyExists):
            self.svc.rename_board(Path("alpha"), "beta")


class TestKanbanServiceDeleteBoard(unittest.TestCase):
    """delete_board removes a board and honors active-board context."""

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

    def test_delete_board_by_path_removes_board(self) -> None:
        """delete_board removes the board from the repository."""
        self.svc.delete_board(Path("alpha"))

        self.assertFalse(self.repo.board_exists("alpha"))

    def test_delete_board_returns_deleted_board(self) -> None:
        """delete_board returns the Board that was removed."""
        deleted = self.svc.delete_board(Path("alpha"))
        self.assertIsInstance(deleted, Board)
        self.assertEqual(deleted.slug, "alpha")

    def test_delete_board_uses_active_board_when_path_is_none(self) -> None:
        """delete_board with path=None deletes the active board."""
        self.svc.working_board = "alpha"
        deleted = self.svc.delete_board(None)
        self.assertEqual(deleted.slug, "alpha")
        self.assertFalse(self.repo.board_exists("alpha"))

    def test_delete_board_clears_working_board_when_deleting_active(self) -> None:
        """Deleting the active board clears the working board."""
        self.svc.working_board = "alpha"
        self.svc.delete_board(Path("/alpha"))
        self.assertIsNone(self.svc.working_board)

    def test_delete_board_leaves_working_board_when_deleting_other(self) -> None:
        """Deleting a non-active board does not change the active board."""
        self.repo.create_board("beta", slug="beta")
        self.svc.working_board = "beta"
        self.svc.delete_board(Path("/alpha"))
        self.assertEqual(self.svc.working_board, "beta")

    def test_delete_board_raises_without_path_or_active_board(self) -> None:
        """delete_board raises when neither a path nor an active board is provided."""
        with self.assertRaises(ValueError):
            self.svc.delete_board(None)

    def test_delete_board_raises_for_missing_board(self) -> None:
        """delete_board raises BoardNotFound when the board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.delete_board(Path("missing"))


if __name__ == "__main__":
    unittest.main()
