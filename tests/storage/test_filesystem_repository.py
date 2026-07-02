"""Tests that FilesystemRepository fully implements KanbanRepository.

These tests do not exercise any I/O — they verify structural completeness:
that the class is a proper subclass, that Python's ABC enforcement allows
instantiation (meaning no abstract method is missing), and that every
abstract method declared on the base class has a concrete override.
"""

from __future__ import annotations

import inspect
import unittest
from pathlib import Path

from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.base import KanbanRepository


class TestFilesystemRepositoryInterface(unittest.TestCase):
    """Structural contract tests for FilesystemRepository."""

    def test_is_subclass_of_kanban_repository(self) -> None:
        """FilesystemRepository must be a direct subclass of KanbanRepository."""
        self.assertTrue(issubclass(FilesystemRepository, KanbanRepository))

    def test_can_be_instantiated(self) -> None:
        """ABC enforcement: TypeError if any abstract method is unimplemented."""
        repo = FilesystemRepository(root=Path("/tmp"))
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
            if getattr(getattr(FilesystemRepository, name, None), "__isabstractmethod__", False)
        }
        self.assertEqual(
            still_abstract,
            set(),
            f"Abstract methods not overridden in FilesystemRepository: {still_abstract}",
        )


if __name__ == "__main__":
    unittest.main()
