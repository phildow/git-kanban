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

from storage.kanban import KanbanRepository
from storage.memory import InMemoryRepository


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


if __name__ == "__main__":
    unittest.main()
