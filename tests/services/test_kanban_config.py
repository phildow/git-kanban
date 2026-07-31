"""Tests for KanbanService config and userdata methods."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import CONFIG_KEYS, CONFIG_USER_NAME, InvalidConfigKey, KanbanService
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
            git_service=GitService(),
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


class TestKanbanServiceConfigKeys(unittest.TestCase):
    """Only keys in CONFIG_KEYS may be read or written."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
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


class TestKanbanServiceUserdata(unittest.TestCase):
    """get_userdata and set_userdata store and retrieve userdata keys."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
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
