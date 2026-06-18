"""Tests for FilesystemRepository.init_storage.

Verifies the directory and file layout created by init_storage, and that
calling it a second time raises ValueError.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.filesystem import FilesystemRepository


class TestFilesystemInitStorage(unittest.TestCase):
    """init_storage creates the expected directory and file structure."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_kanban_dir_is_created(self) -> None:
        """`.kanban` directory is created at the root."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban").is_dir())

    def test_config_file_is_created(self) -> None:
        """`.kanban/config` file is created."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban" / "config").is_file())

    def test_index_db_file_is_created(self) -> None:
        """`.kanban/index.db` placeholder file is created."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban" / "index.db").is_file())

    def test_kanban_store_boards_dir_is_created(self) -> None:
        """`.kanban-store/boards` directory is created."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban-store" / "boards").is_dir())

    def test_boards_metadata_file_is_created(self) -> None:
        """`.kanban-store/boards/.metadata` file is created."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban-store" / "boards" / ".metadata").is_file())

    def test_raises_when_already_initialized(self) -> None:
        """Calling init_storage a second time raises ValueError."""
        self.repo.init_storage()
        with self.assertRaises(ValueError):
            self.repo.init_storage()


if __name__ == "__main__":
    unittest.main()
