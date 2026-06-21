"""Tests for FilesystemRepository.bootstrap."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.filesystem import FilesystemRepository


class TestFilesystemBootstrap(unittest.TestCase):
    """bootstrap creates the default board and column structure."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_creates_main_board(self) -> None:
        """The main board exists after bootstrap."""
        self.repo.bootstrap()
        self.assertTrue(self.repo.board_exists("main"))

    def test_creates_default_columns(self) -> None:
        """All four standard columns are created under main."""
        self.repo.bootstrap()
        columns = [c.name for c in self.repo.get_columns("main")]
        self.assertEqual(columns, ["todo", "in-progress", "in-review", "done"])

    def test_no_tasks_created(self) -> None:
        """bootstrap creates no tasks; seeding is the service's responsibility."""
        self.repo.bootstrap()
        tasks = self.repo.get_tasks(board="main")
        self.assertEqual(tasks, [])


if __name__ == "__main__":
    unittest.main()
