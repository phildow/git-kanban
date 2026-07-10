"""Tests for InMemoryIndexService search sort order.

None-valued fields always sort last regardless of the reverse flag.
"""

from __future__ import annotations

import unittest
from datetime import date

# from models import Priority
from kanban.index.memory import InMemoryIndexService
from kanban.index.query import SearchQuery, SortField
from tests.index.helpers import make_task, utc


class TestSortByTitle(unittest.TestCase):
    """Default sort is title ascending, case-insensitive."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService()
        for title in ("Banana task", "Apple task", "Cherry task"):
            self.index.upsert_task(make_task(title=title))

    def _titles(self, **kw: object) -> list[str]:
        return [r.task.title for r in self.index.search(SearchQuery(**kw))]

    def test_default_is_title_ascending(self) -> None:
        """SearchQuery() defaults to title ascending."""
        self.assertEqual(self._titles(), ["Apple task", "Banana task", "Cherry task"])

    def test_title_descending(self) -> None:
        """reverse=True reverses title order."""
        self.assertEqual(
            self._titles(sort=SortField.TITLE, reverse=True),
            ["Cherry task", "Banana task", "Apple task"],
        )


class TestSortByPriority(unittest.TestCase):
    """Priority sort order is LOW < MEDIUM < HIGH. None always sorts last."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService()
        self.index.upsert_task(make_task(title="High", priority="high"))
        self.index.upsert_task(make_task(title="Low", priority="low"))
        self.index.upsert_task(make_task(title="Med", priority="medium"))
        self.index.upsert_task(make_task(title="None", priority=None))

    def _titles(self, reverse: bool = False) -> list[str]:
        return [
            r.task.title
            for r in self.index.search(SearchQuery(sort=SortField.PRIORITY, reverse=reverse))
        ]

    def test_ascending_low_to_high_none_last(self) -> None:
        """Ascending: LOW first, HIGH last, None after HIGH."""
        titles = self._titles()
        self.assertLess(titles.index("Low"), titles.index("Med"))
        self.assertLess(titles.index("Med"), titles.index("High"))
        self.assertEqual(titles[-1], "None")

    def test_descending_high_to_low_none_still_last(self) -> None:
        """Descending: HIGH first, LOW last, None still after LOW."""
        titles = self._titles(reverse=True)
        self.assertEqual(titles[0], "High")
        self.assertEqual(titles[-1], "None")


class TestSortByDueDate(unittest.TestCase):
    """Due-date sort: earliest first ascending. None always sorts last."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService()
        self.index.upsert_task(make_task(title="Early", due_date=date(2026, 1, 1)))
        self.index.upsert_task(make_task(title="Late", due_date=date(2026, 12, 31)))
        self.index.upsert_task(make_task(title="No date"))

    def _titles(self, reverse: bool = False) -> list[str]:
        return [
            r.task.title
            for r in self.index.search(SearchQuery(sort=SortField.DUE_DATE, reverse=reverse))
        ]

    def test_ascending_earliest_first_none_last(self) -> None:
        """Ascending: earliest date first, None last."""
        self.assertEqual(self._titles(), ["Early", "Late", "No date"])

    def test_descending_latest_first_none_still_last(self) -> None:
        """Descending: latest date first, None still last."""
        self.assertEqual(self._titles(reverse=True), ["Late", "Early", "No date"])


class TestSortByTimestamps(unittest.TestCase):
    """created_at and updated_at sort chronologically. None always sorts last."""

    def setUp(self) -> None:
        self.index = InMemoryIndexService()
        self.index.upsert_task(
            make_task(title="Old", created_at=utc(2026, 1, 1), updated_at=utc(2026, 1, 1))
        )
        self.index.upsert_task(
            make_task(title="New", created_at=utc(2026, 6, 1), updated_at=utc(2026, 6, 1))
        )
        self.index.upsert_task(make_task(title="No ts"))

    def test_sort_by_created_at_none_last(self) -> None:
        """created_at ascending: oldest first, None last."""
        titles = [
            r.task.title
            for r in self.index.search(SearchQuery(sort=SortField.CREATED_AT))
        ]
        self.assertEqual(titles[0], "Old")
        self.assertEqual(titles[-1], "No ts")

    def test_sort_by_updated_at_none_last(self) -> None:
        """updated_at ascending: oldest first, None last."""
        titles = [
            r.task.title
            for r in self.index.search(SearchQuery(sort=SortField.UPDATED_AT))
        ]
        self.assertEqual(titles[0], "Old")
        self.assertEqual(titles[-1], "No ts")

    def test_created_at_descending_none_still_last(self) -> None:
        """created_at descending: newest first, None still last."""
        titles = [
            r.task.title
            for r in self.index.search(SearchQuery(sort=SortField.CREATED_AT, reverse=True))
        ]
        self.assertEqual(titles[0], "New")
        self.assertEqual(titles[-1], "No ts")
