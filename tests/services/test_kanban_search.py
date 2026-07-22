"""Tests for KanbanService.search."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from kanban.index.memory import InMemoryIndex
from kanban.models import Priority, TaskFilter
from kanban.services.git import GitService
from kanban.services.index import IndexService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceSearch(unittest.TestCase):
    """KanbanService.search returns Task objects from the index service's search results."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.index_service = IndexService(index_base=InMemoryIndex(), repository=self.repo)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=self.index_service,
            git_service=GitService(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_board("beta", slug="beta")
        self.repo.create_column("beta", "todo", slug="todo")

        self.t1 = self.svc.create_task("alpha/todo", TaskCreateParams(title="Fix login bug", assigned_to="alice", priority=Priority.HIGH, tags=["bug", "auth"]),
        )
        self.t2 = self.svc.create_task("alpha/todo", TaskCreateParams(title="Write API docs", assigned_to="bob", priority=Priority.MEDIUM, tags=["docs"]),
        )
        self.t3 = self.svc.create_task("beta/todo", TaskCreateParams(title="Deploy staging", assigned_to="alice", priority=Priority.LOW),
        )

    def test_search_returns_task_instances(self) -> None:
        """search() returns Task objects, not SearchResult wrappers."""
        results = self.svc.search("login")
        self.assertEqual(len(results), 1)
        self.assertIsInstance(results[0], type(self.t1))

    def test_search_matches_title_substring_case_insensitively(self) -> None:
        """search() matches a case-insensitive substring of the title."""
        results = self.svc.search("LOGIN")
        self.assertEqual({t.id for t in results}, {self.t1.id})

    def test_search_scoped_to_board(self) -> None:
        """board= restricts results to tasks in that board."""
        results = self.svc.search("", board="alpha")
        self.assertEqual({t.id for t in results}, {self.t1.id, self.t2.id})

    def test_search_with_filter_narrows_results(self) -> None:
        """A TaskFilter is applied in addition to the text query."""
        results = self.svc.search("", filter=TaskFilter(assigned_to="alice"))
        self.assertEqual({t.id for t in results}, {self.t1.id, self.t3.id})

    def test_search_with_priority_filter(self) -> None:
        """TaskFilter.priority narrows results to that priority level."""
        results = self.svc.search("", filter=TaskFilter(priority=Priority.HIGH))
        self.assertEqual({t.id for t in results}, {self.t1.id})

    def test_search_sort_title_ascending(self) -> None:
        """sort='title' orders results alphabetically by title."""
        results = self.svc.search("", sort="title")
        self.assertEqual([t.id for t in results], [self.t3.id, self.t1.id, self.t2.id])

    def test_search_reverse_flips_sort_order(self) -> None:
        """reverse=True reverses the sort order."""
        results = self.svc.search("", sort="title", reverse=True)
        self.assertEqual([t.id for t in results], [self.t2.id, self.t1.id, self.t3.id])

    def test_search_with_no_matches_returns_empty_list(self) -> None:
        """A query that matches nothing returns an empty list."""
        results = self.svc.search("nonexistent")
        self.assertEqual(results, [])

    def test_search_reflects_out_of_band_index_changes_via_rebuild(self) -> None:
        """search() rebuilds the index first, so it reflects changes not yet upserted."""
        self.index_service.clear()
        results = self.svc.search("login")
        self.assertEqual({t.id for t in results}, {self.t1.id})


if __name__ == "__main__":
    unittest.main()
