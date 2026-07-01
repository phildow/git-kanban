"""Tests for InMemoryIndexService completion-value enumeration."""

from __future__ import annotations

import unittest

from kanban.index.memory import InMemoryIndexService
from kanban.storage.memory import InMemoryRepository
from tests.index.helpers import make_task


class TestListTags(unittest.TestCase):
    """list_tags returns sorted distinct tags, optionally scoped to a board."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService(repository=InMemoryRepository())
        self.index.upsert_task(make_task(board="proj", tags=("bug", "auth")))
        self.index.upsert_task(make_task(title="Task 2", board="proj", tags=("bug", "api")))
        self.index.upsert_task(make_task(title="Task 3", board="ops", tags=("infra",)))

    def test_returns_distinct_values(self) -> None:
        """Duplicate tags across tasks appear only once."""
        self.assertEqual(self.index.list_tags().count("bug"), 1)

    def test_all_boards_by_default(self) -> None:
        """Tags from all boards are included when no board is given."""
        self.assertIn("infra", self.index.list_tags())

    def test_returned_tags_are_sorted(self) -> None:
        """list_tags returns values in sorted order."""
        tags = self.index.list_tags()
        self.assertEqual(tags, sorted(tags))

    def test_scoped_by_board(self) -> None:
        """Tags from other boards are excluded when board= is given."""
        tags = self.index.list_tags(board="proj")
        self.assertNotIn("infra", tags)
        self.assertIn("bug", tags)

    def test_empty_index_returns_empty_list(self) -> None:
        """An empty index yields an empty list."""
        self.assertEqual(InMemoryIndexService(repository=InMemoryRepository()).list_tags(), [])

    def test_tasks_without_tags_contribute_nothing(self) -> None:
        """Tasks with an empty tags tuple do not affect the result."""
        index = InMemoryIndexService(repository=InMemoryRepository())
        index.upsert_task(make_task(tags=()))
        self.assertEqual(index.list_tags(), [])


class TestListAssignedTo(unittest.TestCase):
    """list_assigned_to returns sorted distinct assigned_to values, optionally scoped."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService(repository=InMemoryRepository())
        self.index.upsert_task(make_task(board="proj", assigned_to="alice"))
        self.index.upsert_task(make_task(title="Task 2", board="proj", assigned_to="bob"))
        self.index.upsert_task(make_task(title="Task 3", board="proj", assigned_to="alice"))
        self.index.upsert_task(make_task(title="Task 4", board="ops", assigned_to="carol"))

    def test_returns_distinct_values(self) -> None:
        """Duplicate assigned_to values across tasks appear only once."""
        self.assertEqual(self.index.list_assigned_to(board="proj").count("alice"), 1)

    def test_returned_assigned_to_are_sorted(self) -> None:
        """list_assigned_to returns values in sorted order."""
        assigned_to = self.index.list_assigned_to()
        self.assertEqual(assigned_to, sorted(assigned_to))

    def test_scoped_by_board(self) -> None:
        """Assigned_to from other boards are excluded when board= is given."""
        self.assertNotIn("carol", self.index.list_assigned_to(board="proj"))

    def test_none_assigned_to_excluded(self) -> None:
        """Tasks with no assigned_to do not contribute a None entry."""
        index = InMemoryIndexService(repository=InMemoryRepository())
        index.upsert_task(make_task(assigned_to=None))
        self.assertEqual(index.list_assigned_to(), [])
