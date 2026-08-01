"""Tests for FilesystemRepository.init_storage and init_local_data.

Verifies the directory and file layout created by each, that calling
init_storage a second time raises, and that only the store is required for the
repository to report itself initialized.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from kanban.models.config import (
    CONFIG_DEFAULTS,
    CONFIG_NEW_TASK_INSERT,
    CONFIG_USER_NAME,
    INSERT_BOTTOM,
    INSERT_TOP,
)
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import RepositoryAlreadyInitialized


class TestFilesystemInitStorage(unittest.TestCase):
    """init_storage creates the kanban store directory structure."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_kanban_store_boards_dir_is_created(self) -> None:
        """`.kanban-store/boards` directory is created."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban-store" / "boards").is_dir())

    def test_boards_metadata_file_is_created(self) -> None:
        """`.kanban-store/boards/.metadata` file is created."""
        self.repo.init_storage()
        self.assertTrue((self.root / ".kanban-store" / "boards" / ".metadata").is_file())

    def test_local_data_dir_is_not_created(self) -> None:
        """`.kanban` is left to init_local_data and is not created here."""
        self.repo.init_storage()
        self.assertFalse((self.root / ".kanban").exists())

    def test_is_initialized_without_local_data(self) -> None:
        """The store alone is enough for the repository to report itself initialized."""
        self.repo.init_storage()
        self.assertTrue(self.repo.is_initialized)

    def test_is_not_initialized_before_init(self) -> None:
        """A repository with no store reports itself uninitialized."""
        self.assertFalse(self.repo.is_initialized)

    def test_raises_when_already_initialized(self) -> None:
        """Calling init_storage a second time raises RepositoryAlreadyInitialized."""
        self.repo.init_storage()
        with self.assertRaises(RepositoryAlreadyInitialized):
            self.repo.init_storage()


class TestFilesystemInitLocalData(unittest.TestCase):
    """init_local_data creates the local data directory and its files."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_kanban_dir_is_created(self) -> None:
        """`.kanban` directory is created at the root."""
        self.repo.init_local_data()
        self.assertTrue((self.root / ".kanban").is_dir())

    def test_config_file_is_created(self) -> None:
        """`.kanban/config` file is created."""
        self.repo.init_local_data()
        self.assertTrue((self.root / ".kanban" / "config").is_file())

    def test_history_file_is_created(self) -> None:
        """`.kanban/history` file is created."""
        self.repo.init_local_data()
        self.assertTrue((self.root / ".kanban" / "history").is_file())

    def test_userdata_file_is_created(self) -> None:
        """`.kanban/userdata` file is created."""
        self.repo.init_local_data()
        self.assertTrue((self.root / ".kanban" / "userdata").is_file())

    def test_index_db_file_is_created(self) -> None:
        """`.kanban/index.db` placeholder file is created."""
        self.repo.init_local_data()
        self.assertTrue((self.root / ".kanban" / "index.db").is_file())

    def test_has_local_data_is_false_before_init(self) -> None:
        """has_local_data is False before local data is created."""
        self.assertFalse(self.repo.has_local_data)

    def test_has_local_data_is_true_after_init(self) -> None:
        """has_local_data is True once local data is created."""
        self.repo.init_local_data()
        self.assertTrue(self.repo.has_local_data)

    def test_does_not_create_store(self) -> None:
        """Local data setup leaves the kanban store alone."""
        self.repo.init_local_data()
        self.assertFalse((self.root / ".kanban-store").exists())

    def test_is_idempotent(self) -> None:
        """Calling init_local_data again neither raises nor clears existing data."""
        self.repo.init_local_data()
        self.repo.set_config("app.name", "kanban")
        self.repo.init_local_data()
        self.assertEqual(self.repo.get_config("app.name"), "kanban")


class TestFilesystemInitLocalDataDefaults(unittest.TestCase):
    """init_local_data writes the default value of every setting that has one."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_defaults_are_written(self) -> None:
        """Every default is readable from the new config file."""
        self.repo.init_local_data()

        for keypath, value in CONFIG_DEFAULTS.items():
            self.assertEqual(self.repo.get_config(keypath), value)

    def test_new_task_insert_defaults_to_bottom(self) -> None:
        """New tasks are configured to go to the bottom of their column."""
        self.repo.init_local_data()

        self.assertEqual(self.repo.get_config(CONFIG_NEW_TASK_INSERT), INSERT_BOTTOM)

    def test_defaults_are_written_to_the_file(self) -> None:
        """The values are in the config file itself, not only in memory."""
        self.repo.init_local_data()
        config = (self.root / ".kanban" / "config").read_text(encoding="utf-8")

        self.assertIn("new-task", config)
        self.assertIn(INSERT_BOTTOM, config)

    def test_a_changed_setting_is_not_overwritten(self) -> None:
        """A setting the user has changed survives a later init_local_data."""
        self.repo.init_local_data()
        self.repo.set_config(CONFIG_NEW_TASK_INSERT, INSERT_TOP)
        self.repo.init_local_data()

        self.assertEqual(self.repo.get_config(CONFIG_NEW_TASK_INSERT), INSERT_TOP)

    def test_keys_without_a_default_stay_unset(self) -> None:
        """A setting with no default is left for the user to set."""
        self.repo.init_local_data()

        self.assertIsNone(self.repo.get_config(CONFIG_USER_NAME))


if __name__ == "__main__":
    unittest.main()
