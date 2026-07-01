"""Tests for FilesystemRepository.rename_board."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.models import Board
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.kanban import BoardNotFound, BoardAlreadyExists


class TestFilesystemRenameBoard(unittest.TestCase):
    """rename_board renames the board directory and returns the updated Board."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self._make_board("alpha")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_board(self, slug: str, name: str | None = None) -> None:
        """Create a board directory with the metadata fields required by rename_board."""
        (self.repo.boards_dir / slug).mkdir()
        display_name = name or slug
        self.repo.set_board_metadata(slug, "fields.name", display_name)
        self.repo.set_board_metadata(slug, "fields.slug", slug)
        self.repo.set_board_metadata(slug, "fields.id", str(uuid4()))

    def test_renames_directory(self) -> None:
        """Old directory is gone and new directory exists after rename."""
        self.repo.rename_board("alpha", "beta", new_slug="beta")
        self.assertFalse((self.repo.boards_dir / "alpha").exists())
        self.assertTrue((self.repo.boards_dir / "beta").is_dir())

    def test_returns_board_with_new_name(self) -> None:
        """Returns a Board with the new name."""
        board = self.repo.rename_board("alpha", "beta", new_slug="beta")
        self.assertIsInstance(board, Board)
        self.assertEqual(board.name, "beta")

    def test_raises_when_source_missing(self) -> None:
        """Raises BoardNotFound when the source board does not exist."""
        with self.assertRaises(BoardNotFound):
            self.repo.rename_board("missing", "beta", new_slug="beta")

    def test_raises_when_target_exists(self) -> None:
        """Raises BoardAlreadyExists when a board with the new name already exists."""
        (self.repo.boards_dir / "beta").mkdir()
        with self.assertRaises(BoardAlreadyExists):
            self.repo.rename_board("alpha", "beta", new_slug="beta")

    def test_preserves_column_directories(self) -> None:
        """Column subdirectories are preserved under the renamed board."""
        (self.repo.boards_dir / "alpha" / "todo").mkdir()
        (self.repo.boards_dir / "alpha" / "done").mkdir()
        self.repo.rename_board("alpha", "beta", new_slug="beta")
        self.assertTrue((self.repo.boards_dir / "beta" / "todo").is_dir())
        self.assertTrue((self.repo.boards_dir / "beta" / "done").is_dir())


if __name__ == "__main__":
    unittest.main()
