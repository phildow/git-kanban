"""Tests for InMemoryIndex search filtering."""

from __future__ import annotations

import unittest
from datetime import date

# from models import Priority
from kanban.index.memory import InMemoryIndex
from kanban.index.query import SearchQuery
from tests.index.helpers import make_task


class TestSearchFilters(unittest.TestCase):
    """Each SearchQuery field narrows results independently (AND semantics)."""

    def setUp(self) -> None:
        self.index = InMemoryIndex()
        self.t1 = make_task(
            title="Fix login bug",
            board="proj",
            column="todo",
            assigned_to="alice",
            priority="high", # Priority.HIGH,
            tags=("bug", "auth"),
            created_by="alice",
            due_date=date(2026, 6, 10),
            body="Users report intermittent failures when authenticating via SSO.",
        )
        self.t2 = make_task(
            title="Write API docs",
            board="proj",
            column="in-progress",
            assigned_to="bob",
            priority="medium", # Priority.MEDIUM,
            tags=("docs",),
            created_by="bob",
            due_date=date(2026, 7, 1),
            body="Document the /tasks endpoint and pagination behavior.",
        )
        self.t3 = make_task(
            title="Deploy staging",
            board="ops",
            column="todo",
            assigned_to="alice",
            priority="low", # Priority.LOW,
            tags=("infra",),
            created_by="carol",
            body="Rotate the staging credentials before deploying.",
        )
        for t in (self.t1, self.t2, self.t3):
            self.index.upsert_task(t)

    def _ids(self, query: SearchQuery) -> set:
        """Return the set of task ids from a search result."""
        return {r.task.id for r in self.index.search(query)}

    def test_no_filters_returns_all(self) -> None:
        """An empty SearchQuery returns every indexed task."""
        self.assertEqual(self._ids(SearchQuery()), {self.t1.id, self.t2.id, self.t3.id})

    def test_filter_by_board(self) -> None:
        """board= restricts results to that board."""
        self.assertEqual(self._ids(SearchQuery(board="proj")), {self.t1.id, self.t2.id})

    def test_filter_by_column(self) -> None:
        """column= restricts results to that column within the board."""
        self.assertEqual(self._ids(SearchQuery(board="proj", column="todo")), {self.t1.id})

    def test_filter_by_assigned_to(self) -> None:
        """assigned_to= returns only tasks assigned to that person."""
        self.assertEqual(self._ids(SearchQuery(assigned_to="alice")), {self.t1.id, self.t3.id})

    def test_filter_by_priority(self) -> None:
        """priority= returns only tasks at that priority level."""
        self.assertEqual(self._ids(SearchQuery(priority="high")), {self.t1.id})

    def test_filter_by_single_tag(self) -> None:
        """tags= with one tag returns tasks that include it."""
        self.assertEqual(self._ids(SearchQuery(tags=("bug",))), {self.t1.id})

    def test_filter_by_multiple_tags_requires_all(self) -> None:
        """Multiple tags in tags= are AND-ed together."""
        self.assertEqual(self._ids(SearchQuery(tags=("bug", "auth"))), {self.t1.id})

    def test_filter_by_tags_with_partial_miss(self) -> None:
        """A task missing any required tag is excluded."""
        self.assertEqual(self._ids(SearchQuery(tags=("bug", "docs"))), set())

    def test_filter_by_created_by(self) -> None:
        """created_by= returns only tasks created by that person."""
        self.assertEqual(self._ids(SearchQuery(created_by="carol")), {self.t3.id})

    def test_filter_due_before_is_exclusive(self) -> None:
        """due_before= excludes tasks due on or after that date."""
        self.assertEqual(self._ids(SearchQuery(due_before=date(2026, 7, 1))), {self.t1.id})

    def test_filter_due_after_is_exclusive(self) -> None:
        """due_after= excludes tasks due on or before that date."""
        self.assertEqual(self._ids(SearchQuery(due_after=date(2026, 6, 10))), {self.t2.id})

    def test_filter_due_before_excludes_no_due_date(self) -> None:
        """Tasks with no due_date are excluded by date filters."""
        self.assertNotIn(self.t3.id, self._ids(SearchQuery(due_before=date(2026, 12, 31))))

    def test_filter_text_matches_title_substring(self) -> None:
        """text= matches case-insensitively as a substring of the title."""
        self.assertEqual(self._ids(SearchQuery(text="login")), {self.t1.id})

    def test_filter_text_is_case_insensitive(self) -> None:
        """text= is matched case-insensitively."""
        self.assertEqual(self._ids(SearchQuery(text="WRITE")), {self.t2.id})

    def test_filter_text_matches_body_substring(self) -> None:
        """text= matches as a substring of the body when absent from the title."""
        self.assertEqual(self._ids(SearchQuery(text="SSO")), {self.t1.id})

    def test_filter_text_matches_body_is_case_insensitive(self) -> None:
        """text= body matching is case-insensitive."""
        self.assertEqual(self._ids(SearchQuery(text="PAGINATION")), {self.t2.id})

    def test_filter_text_matches_body_substring_not_whole_word(self) -> None:
        """text= matches a body substring even when it isn't a whole word."""
        self.assertEqual(self._ids(SearchQuery(text="credential")), {self.t3.id})

    def test_filter_text_with_no_title_or_body_match_returns_empty(self) -> None:
        """text= with no match in any task's title or body returns nothing."""
        self.assertEqual(self._ids(SearchQuery(text="nonexistent")), set())

    def test_multiple_filters_are_anded(self) -> None:
        """Multiple filters are combined with AND; all must be satisfied."""
        self.assertEqual(self._ids(SearchQuery(board="proj", assigned_to="alice")), {self.t1.id})

    def test_search_result_score_is_none(self) -> None:
        """InMemoryIndex always produces score=None (no bm25 ranking)."""
        self.assertTrue(all(r.score is None for r in self.index.search(SearchQuery())))
