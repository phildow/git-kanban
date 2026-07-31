"""Tests for FilesystemRepository.get_config, set_config, get_userdata, set_userdata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.storage.filesystem import FilesystemRepository


class TestFilesystemGetConfig(unittest.TestCase):
    """get_config returns values from the INI config file or None when absent."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.init_local_data()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_value_for_existing_key(self) -> None:
        """Returns the stored value when section and key both exist."""
        self.repo.set_config("app.name", "kanban")
        self.assertEqual(self.repo.get_config("app.name"), "kanban")

    def test_returns_none_for_missing_key(self) -> None:
        """Returns None when the section exists but the key does not."""
        self.assertIsNone(self.repo.get_config("user-context.nonexistent"))

    def test_returns_none_for_missing_section(self) -> None:
        """Returns None when the section does not exist."""
        self.assertIsNone(self.repo.get_config("no-such-section.key"))

    def test_raises_for_invalid_keypath(self) -> None:
        """Raises KeyError when the keypath has no dot separator."""
        with self.assertRaises(KeyError):
            self.repo.get_config("nodot")


class TestFilesystemGetUserdata(unittest.TestCase):
    """get_userdata returns values from the userdata INI file or None when absent."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.init_local_data()
        self.repo.set_userdata("user-context.board", "alpha")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_value_for_existing_key(self) -> None:
        """Returns the stored value when section and key both exist."""
        self.assertEqual(self.repo.get_userdata("user-context.board"), "alpha")

    def test_returns_none_for_missing_key(self) -> None:
        """Returns None when the section exists but the key does not."""
        self.assertIsNone(self.repo.get_userdata("user-context.nonexistent"))

    def test_returns_none_for_missing_section(self) -> None:
        """Returns None when the section does not exist."""
        self.assertIsNone(self.repo.get_userdata("no-such-section.key"))

    def test_raises_for_invalid_keypath(self) -> None:
        """Raises KeyError when the keypath has no dot separator."""
        with self.assertRaises(KeyError):
            self.repo.get_userdata("nodot")


if __name__ == "__main__":
    unittest.main()
