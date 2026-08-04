"""Tests for FilesystemRepository.get_board."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.models import ARCHIVE_COLUMN_SLUG, Board, ROLE_ARCHIVE
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import BoardNotFound


class TestFilesystemGetBoard(unittest.TestCase):
    """get_board finds a board directory and returns a Board, or raises."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_board(self, slug: str, name: str | None = None) -> None:
        """Create a board directory with the metadata fields required by get_board."""
        (self.repo.boards_dir / slug).mkdir()
        display_name = name or slug
        self.repo.set_board_metadata(slug, "fields.name", display_name)
        self.repo.set_board_metadata(slug, "fields.slug", slug)
        self.repo.set_board_metadata(slug, "fields.id", str(uuid4()))

    def test_returns_board_for_existing_directory(self) -> None:
        """A board directory that exists is returned as a Board."""
        self._make_board("alpha")
        board = self.repo.get_board("alpha")
        self.assertIsInstance(board, Board)
        self.assertEqual(board.name, "alpha")

    def test_raises_when_board_missing(self) -> None:
        """Requesting a non-existent board raises BoardNotFound."""
        with self.assertRaises(BoardNotFound):
            self.repo.get_board("missing")

    def test_raises_for_hidden_directory(self) -> None:
        """Hidden directories are not valid boards."""
        (self.repo.boards_dir / ".hidden").mkdir()
        with self.assertRaises(BoardNotFound):
            self.repo.get_board(".hidden")

    def test_raises_when_path_is_a_file(self) -> None:
        """A file with the board name is not a valid board."""
        (self.repo.boards_dir / "not-a-board").touch()
        with self.assertRaises(BoardNotFound):
            self.repo.get_board("not-a-board")

    def test_returns_board_with_empty_columns(self) -> None:
        """Returned Board has zero counts when no columns/tasks exist."""
        self._make_board("alpha")
        board = self.repo.get_board("alpha")
        self.assertEqual(board.column_count, 0)
        self.assertEqual(board.task_count, 0)

    def test_returns_board_with_column_and_task_counts(self) -> None:
        """Returned Board includes counts derived from the board directory."""
        self._make_board("alpha")

        todo = self.repo.boards_dir / "alpha" / "todo"
        done = self.repo.boards_dir / "alpha" / "done"
        todo.mkdir()
        done.mkdir()

        (todo / "first.md").touch()
        (done / "second.md").touch()
        (done / ".metadata").touch()

        board = self.repo.get_board("alpha")

        self.assertEqual(board.column_count, 2)
        self.assertEqual(board.task_count, 2)

    def _make_archive(self, board: str) -> Path:
        """Create an archive column on a board and return its directory."""
        archive = self.repo.boards_dir / board / ARCHIVE_COLUMN_SLUG
        archive.mkdir()
        self.repo.set_column_metadata(board, ARCHIVE_COLUMN_SLUG, "fields.role", ROLE_ARCHIVE)
        return archive

    def test_task_count_excludes_archived_tasks(self) -> None:
        """Tasks in the archive column are left out of task_count."""
        self._make_board("alpha")

        todo = self.repo.boards_dir / "alpha" / "todo"
        todo.mkdir()
        (todo / "first.md").touch()

        archive = self._make_archive("alpha")
        (archive / "second.md").touch()

        board = self.repo.get_board("alpha")

        self.assertEqual(board.task_count, 1)

    def test_archived_task_count_counts_the_archive_column(self) -> None:
        """archived_task_count is the number of tasks in the archive column."""
        self._make_board("alpha")

        archive = self._make_archive("alpha")
        (archive / "first.md").touch()
        (archive / "second.md").touch()

        board = self.repo.get_board("alpha")

        self.assertEqual(board.archived_task_count, 2)

    def test_archived_task_count_is_zero_without_an_archive(self) -> None:
        """A board with no archive column reports no archived tasks."""
        self._make_board("alpha")

        todo = self.repo.boards_dir / "alpha" / "todo"
        todo.mkdir()
        (todo / "first.md").touch()

        board = self.repo.get_board("alpha")

        self.assertEqual(board.archived_task_count, 0)

    def test_archive_is_found_by_role_not_slug(self) -> None:
        """A renamed archive column is still counted as the archive."""
        self._make_board("alpha")

        archive = self.repo.boards_dir / "alpha" / "cold-storage"
        archive.mkdir()
        self.repo.set_column_metadata("alpha", "cold-storage", "fields.role", ROLE_ARCHIVE)
        (archive / "first.md").touch()

        board = self.repo.get_board("alpha")

        self.assertEqual(board.task_count, 0)
        self.assertEqual(board.archived_task_count, 1)


if __name__ == "__main__":
    unittest.main()
