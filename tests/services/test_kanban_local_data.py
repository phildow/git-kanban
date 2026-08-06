"""Tests for lazy local data creation during KanbanService construction.

The kanban store may exist without the .kanban local data directory, e.g. on a
fresh clone. The service recreates it on construction rather than requiring the
repository to be initialized again.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from kanban.index.memory import InMemoryIndex
from kanban.services.index import IndexService
from kanban.services.kanban import KanbanService
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceLazyLocalData(unittest.TestCase):
    """Local data is created on construction when the store exists without it."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_service(self) -> KanbanService:
        """Return a service backed by the test's filesystem repository."""
        return KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            change_tracking=MagicMock(),
        )

    def test_local_data_created_for_store_without_it(self) -> None:
        """A store-only repository gets its .kanban directory on construction."""
        self.repo.init_storage()
        self._make_service()

        self.assertTrue((self.root / ".kanban").is_dir())

    def test_userdata_file_created_for_store_without_it(self) -> None:
        """The recreated local data includes the userdata file."""
        self.repo.init_storage()
        self._make_service()

        self.assertTrue((self.root / ".kanban" / "userdata").is_file())

    def test_existing_local_data_is_preserved(self) -> None:
        """Existing config values survive construction."""
        self.repo.init_storage()
        self.repo.init_local_data()
        self.repo.set_config("app.name", "kanban")
        self._make_service()

        self.assertEqual(self.repo.get_config("app.name"), "kanban")

    def test_no_local_data_created_when_uninitialized(self) -> None:
        """Without a store, construction leaves the root untouched."""
        self._make_service()

        self.assertFalse((self.root / ".kanban").exists())

    def test_failure_to_create_local_data_is_not_raised(self) -> None:
        """An OSError while creating local data is logged, not propagated."""
        self.repo.init_storage()
        self.repo.init_local_data = MagicMock(side_effect=OSError("read-only filesystem"))

        with self.assertLogs(level="WARNING"):
            self._make_service()


class TestKanbanServiceLocalDataInMemory(unittest.TestCase):
    """A repository without local data is constructed without error."""

    def test_in_memory_repository_construction(self) -> None:
        """The in-memory repository's no-op init_local_data does not break construction."""
        repo = InMemoryRepository(root=Path("."))
        repo.init_storage()
        svc = KanbanService(repository=repo, index_service=MagicMock(), change_tracking=MagicMock())

        self.assertFalse(svc.has_local_data)


if __name__ == "__main__":
    unittest.main()
