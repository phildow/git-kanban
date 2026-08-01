"""Tests that InMemoryRepository fully implements KanbanRepository.

Structural completeness checks: correct subclass, ABC instantiation
enforcement, and no abstract methods left unimplemented.
"""

from __future__ import annotations

import inspect
import tempfile
import unittest

from pathlib import Path
from uuid import uuid4

from kanban.models.config import CONFIG_DEFAULTS, CONFIG_NEW_TASK_INSERT, INSERT_TOP
from kanban.storage.base import KanbanRepository
from kanban.storage.memory import InMemoryRepository


class TestInMemoryRepositoryInterface(unittest.TestCase):
    """Structural contract tests for InMemoryRepository."""

    def test_is_subclass_of_kanban_repository(self) -> None:
        """InMemoryRepository must be a direct subclass of KanbanRepository."""
        self.assertTrue(issubclass(InMemoryRepository, KanbanRepository))

    def test_can_be_instantiated(self) -> None:
        """ABC enforcement: TypeError if any abstract method is unimplemented."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        self.assertIsInstance(repo, KanbanRepository)

    def test_all_abstract_methods_are_overridden(self) -> None:
        """Every @abstractmethod on KanbanRepository has a concrete override."""
        abstract_methods = {
            name
            for name, fn in inspect.getmembers(KanbanRepository, predicate=inspect.isfunction)
            if getattr(fn, "__isabstractmethod__", False)
        }
        still_abstract = {
            name
            for name in abstract_methods
            if getattr(getattr(InMemoryRepository, name, None), "__isabstractmethod__", False)
        }
        self.assertEqual(
            still_abstract,
            set(),
            f"Abstract methods not overridden in InMemoryRepository: {still_abstract}",
        )


class TestInMemoryRepositoryLocalData(unittest.TestCase):
    """init_local_data seeds the same defaults the filesystem repository writes."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)

    def test_config_starts_empty(self) -> None:
        """Nothing is configured before local data is initialized."""
        self.assertIsNone(self.repo.get_config(CONFIG_NEW_TASK_INSERT))

    def test_defaults_are_seeded(self) -> None:
        """Every default is readable once local data is initialized."""
        self.repo.init_local_data()

        for keypath, value in CONFIG_DEFAULTS.items():
            self.assertEqual(self.repo.get_config(keypath), value)

    def test_a_changed_setting_is_not_overwritten(self) -> None:
        """A setting already carrying a value survives a later call."""
        self.repo.init_local_data()
        self.repo.set_config(CONFIG_NEW_TASK_INSERT, INSERT_TOP)
        self.repo.init_local_data()

        self.assertEqual(self.repo.get_config(CONFIG_NEW_TASK_INSERT), INSERT_TOP)


if __name__ == "__main__":
    unittest.main()
