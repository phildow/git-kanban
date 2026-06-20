"""Tests for FilesystemRepository.get_board_metadata and set_board_metadata."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from storage.filesystem import FilesystemRepository


class TestFilesystemBoardMetadata(unittest.TestCase):
    """Values written with set_board_metadata can be read back with get_board_metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("alpha")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_written_value_is_readable(self) -> None:
        """A value written with set_board_metadata is returned by get_board_metadata."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha Board")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "Alpha Board")

    def test_multiple_keys_in_same_section(self) -> None:
        """Multiple keys in the same section are stored and retrieved independently."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.repo.set_board_metadata("alpha", "info.description", "My board")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "Alpha")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.description"), "My board")

    def test_multiple_sections(self) -> None:
        """Keys in different sections are stored and retrieved independently."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.repo.set_board_metadata("alpha", "settings.color", "blue")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "Alpha")
        self.assertEqual(self.repo.get_board_metadata("alpha", "settings.color"), "blue")

    def test_overwrite_existing_value(self) -> None:
        """Writing to an existing key replaces the previous value."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Old")
        self.repo.set_board_metadata("alpha", "info.display-name", "New")
        self.assertEqual(self.repo.get_board_metadata("alpha", "info.display-name"), "New")

    def test_set_none_removes_key(self) -> None:
        """Setting a value to None removes the key; subsequent reads return None."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.repo.set_board_metadata("alpha", "info.display-name", None)
        self.assertIsNone(self.repo.get_board_metadata("alpha", "info.display-name"))

    def test_returns_none_for_missing_key(self) -> None:
        """Returns None when the section exists but the key does not."""
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.assertIsNone(self.repo.get_board_metadata("alpha", "info.nonexistent"))

    def test_returns_none_for_missing_section(self) -> None:
        """Returns None when neither section nor key has been written."""
        self.assertIsNone(self.repo.get_board_metadata("alpha", "no-such-section.key"))

    def test_metadata_is_scoped_to_board(self) -> None:
        """Metadata written for one board is not visible on another board."""
        self.repo.create_board("beta")
        self.repo.set_board_metadata("alpha", "info.display-name", "Alpha")
        self.assertIsNone(self.repo.get_board_metadata("beta", "info.display-name"))

    def test_raises_for_invalid_keypath(self) -> None:
        """Raises KeyError when the keypath has no dot separator."""
        with self.assertRaises(KeyError):
            self.repo.get_board_metadata("alpha", "nodot")
        with self.assertRaises(KeyError):
            self.repo.set_board_metadata("alpha", "nodot", "value")


if __name__ == "__main__":
    unittest.main()
