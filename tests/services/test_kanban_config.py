"""Tests for KanbanService config and userdata methods."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import KanbanService
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
        self.assertIsNone(self.svc.get_config("name"))

    def test_set_config_persists_value(self) -> None:
        """set_config stores the value so get_config returns it."""
        self.svc.set_config("name", "Philip")

        self.assertEqual(self.svc.get_config("name"), "Philip")

    def test_set_config_returns_stored_value(self) -> None:
        """set_config returns the stored value after writing it."""
        result = self.svc.set_config("name", "Philip")

        self.assertEqual(result, "Philip")

    def test_set_config_overwrites_previous_value(self) -> None:
        """Setting a key twice replaces the earlier value."""
        self.svc.set_config("name", "Philip")
        self.svc.set_config("name", "Alice")

        self.assertEqual(self.svc.get_config("name"), "Alice")


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
