"""Tests for KanbanService config and userdata methods."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import (
    CONFIG_DEFAULTS,
    CONFIG_KEYS,
    CONFIG_NEW_TASK_INSERT,
    CONFIG_USER_NAME,
    INSERT_BOTTOM,
    INSERT_TOP,
    InvalidConfigKey,
    InvalidConfigValue,
    KanbanService,
)
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceConfig(unittest.TestCase):
    """get_config and set_config store and retrieve config keys."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_get_config_returns_none_for_unset_key(self) -> None:
        """get_config returns None when the key has never been set."""
        self.assertIsNone(self.svc.get_config("user.name"))

    def test_set_config_persists_value(self) -> None:
        """set_config stores the value so get_config returns it."""
        self.svc.set_config("user.name", "Philip")

        self.assertEqual(self.svc.get_config("user.name"), "Philip")

    def test_set_config_returns_stored_value(self) -> None:
        """set_config returns the stored value after writing it."""
        result = self.svc.set_config("user.name", "Philip")

        self.assertEqual(result, "Philip")

    def test_set_config_overwrites_previous_value(self) -> None:
        """Setting a key twice replaces the earlier value."""
        self.svc.set_config("user.name", "Philip")
        self.svc.set_config("user.name", "Alice")

        self.assertEqual(self.svc.get_config("user.name"), "Alice")


class TestKanbanServiceListConfig(unittest.TestCase):
    """list_config reports every supported key with its current value."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_lists_every_supported_key(self) -> None:
        """The result covers exactly the supported key set."""
        self.assertEqual(set(self.svc.list_config()), set(CONFIG_KEYS))

    def test_unset_keys_map_to_none(self) -> None:
        """A key that has never been set maps to None."""
        self.assertIsNone(self.svc.list_config()[CONFIG_USER_NAME])

    def test_reports_stored_values(self) -> None:
        """A key that has been set maps to its stored value."""
        self.svc.set_config(CONFIG_USER_NAME, "Philip")

        self.assertEqual(self.svc.list_config()[CONFIG_USER_NAME], "Philip")

    def test_keys_are_sorted(self) -> None:
        """Keys are returned in sorted keypath order."""
        keys = list(self.svc.list_config())

        self.assertEqual(keys, sorted(keys))


class TestKanbanServiceConfigKeys(unittest.TestCase):
    """Only keys in CONFIG_KEYS may be read or written."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_user_name_is_a_supported_key(self) -> None:
        """user.name is one of the supported config keys."""
        self.assertIn(CONFIG_USER_NAME, CONFIG_KEYS)

    def test_set_config_rejects_unknown_key(self) -> None:
        """set_config raises InvalidConfigKey for a key outside the supported set."""
        with self.assertRaises(InvalidConfigKey):
            self.svc.set_config("user.nickname", "Phil")

    def test_get_config_rejects_unknown_key(self) -> None:
        """get_config raises InvalidConfigKey for a key outside the supported set."""
        with self.assertRaises(InvalidConfigKey):
            self.svc.get_config("user.nickname")

    def test_unknown_key_is_not_written(self) -> None:
        """A rejected set_config leaves nothing in the repository."""
        with self.assertRaises(InvalidConfigKey):
            self.svc.set_config("user.nickname", "Phil")

        self.assertIsNone(self.repo.get_config("user.nickname"))

    def test_new_task_insert_is_a_supported_key(self) -> None:
        """new-task.insert is one of the supported config keys."""
        self.assertIn(CONFIG_NEW_TASK_INSERT, CONFIG_KEYS)


class TestKanbanServiceConfigValues(unittest.TestCase):
    """A key drawing its values from a fixed set only accepts one of them."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_top_is_accepted(self) -> None:
        """new-task.insert accepts top."""
        self.assertEqual(self.svc.set_config(CONFIG_NEW_TASK_INSERT, INSERT_TOP), INSERT_TOP)

    def test_bottom_is_accepted(self) -> None:
        """new-task.insert accepts bottom."""
        self.assertEqual(
            self.svc.set_config(CONFIG_NEW_TASK_INSERT, INSERT_BOTTOM), INSERT_BOTTOM
        )

    def test_other_values_are_refused(self) -> None:
        """Anything else raises InvalidConfigValue."""
        with self.assertRaises(InvalidConfigValue):
            self.svc.set_config(CONFIG_NEW_TASK_INSERT, "sideways")

    def test_refused_value_is_not_written(self) -> None:
        """A rejected value leaves the setting as it was."""
        self.svc.set_config(CONFIG_NEW_TASK_INSERT, INSERT_TOP)
        with self.assertRaises(InvalidConfigValue):
            self.svc.set_config(CONFIG_NEW_TASK_INSERT, "sideways")

        self.assertEqual(self.svc.get_config(CONFIG_NEW_TASK_INSERT), INSERT_TOP)

    def test_free_text_keys_are_unconstrained(self) -> None:
        """A key with no fixed value set takes whatever it is given."""
        self.assertEqual(self.svc.set_config(CONFIG_USER_NAME, "anything at all"),
                         "anything at all")

    def test_every_default_is_a_permitted_value(self) -> None:
        """The shipped defaults satisfy their own keys' constraints."""
        for keypath, value in CONFIG_DEFAULTS.items():
            self.assertEqual(self.svc.set_config(keypath, value), value)


class TestKanbanServiceUserdata(unittest.TestCase):
    """get_userdata and set_userdata store and retrieve userdata keys."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(GitChangeTracker()),
        )

    def test_get_userdata_returns_none_for_unset_key(self) -> None:
        """get_userdata returns None when the key has never been set."""
        self.assertIsNone(self.svc.get_userdata("editor"))

    def test_set_userdata_persists_value(self) -> None:
        """set_userdata stores the value so get_userdata returns it."""
        self.svc.set_userdata("editor", "vim")

        self.assertEqual(self.svc.get_userdata("editor"), "vim")

    def test_set_userdata_none_clears_value(self) -> None:
        """set_userdata with value=None removes the stored key."""
        self.svc.set_userdata("editor", "vim")
        self.svc.set_userdata("editor", None)

        self.assertIsNone(self.svc.get_userdata("editor"))


if __name__ == "__main__":
    unittest.main()
