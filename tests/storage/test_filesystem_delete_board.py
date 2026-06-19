"""Tests for FilesystemRepository.delete_board."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.filesystem import FilesystemRepository
from storage.kanban import BoardNotFound


class TestFilesystemDeleteBoard(unittest.TestCase):
    """delete_board removes the board directory tree or raises BoardNotFound."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("alpha")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_removes_board_directory(self) -> None:
        """Board directory no longer exists after deletion."""
        self.repo.delete_board("alpha")
        self.assertFalse((self.repo.boards_dir / "alpha").exists())

    def test_removes_nested_contents(self) -> None:
        """Column subdirectories and files inside the board are also removed."""
        (self.repo.boards_dir / "alpha" / "todo").mkdir()
        (self.repo.boards_dir / "alpha" / "todo" / "task.md").touch()
        self.repo.delete_board("alpha")
        self.assertFalse((self.repo.boards_dir / "alpha").exists())

    def test_does_not_affect_other_boards(self) -> None:
        """Deleting one board leaves other boards untouched."""
        (self.repo.boards_dir / "beta").mkdir()
        self.repo.delete_board("alpha")
        self.assertTrue((self.repo.boards_dir / "beta").is_dir())

    def test_raises_when_board_missing(self) -> None:
        """Raises BoardNotFound when no board with that name exists."""
        with self.assertRaises(BoardNotFound):
            self.repo.delete_board("missing")


if __name__ == "__main__":
    unittest.main()
