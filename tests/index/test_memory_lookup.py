"""Tests for InMemoryIndex path lookups and title search."""

from __future__ import annotations

import unittest
from pathlib import Path
from uuid import uuid4

from kanban.index.memory import InMemoryIndex
from tests.index.helpers import make_task


class TestGetPath(unittest.TestCase):
    """get_path returns the indexed path for a known id, or None."""

    def setUp(self) -> None:
        self.index = InMemoryIndex()

    def test_returns_task_path(self) -> None:
        """Path returned matches task.path."""
        task = make_task(board="ops", column="in-progress")
        self.index.upsert_task(task)
        expected = Path("/ops/in-progress/fix-login-bug")
        self.assertEqual(self.index.get_path(task.id), expected)

    def test_unknown_id_returns_none(self) -> None:
        """None is returned for an id that has never been indexed."""
        self.assertIsNone(self.index.get_path(uuid4()))


class TestFindByTitle(unittest.TestCase):
    """find_by_title uses exact prefix matching, case-sensitive."""

    def setUp(self) -> None:
        self.index = InMemoryIndex()
        self.fix_login = make_task(title="Fix login bug", board="proj", column="todo")
        self.fix_certs = make_task(title="Fix certs", board="ops", column="todo")
        self.write_docs = make_task(title="Write API docs", board="proj", column="todo")
        self.add_rate = make_task(title="Add rate limiting", board="proj", column="in-progress")
        for t in (self.fix_login, self.fix_certs, self.write_docs, self.add_rate):
            self.index.upsert_task(t)

    def test_prefix_returning_single_match(self) -> None:
        """A prefix that matches exactly one title returns that task."""
        results = self.index.find_by_title("Write")
        self.assertEqual([t.id for t in results], [self.write_docs.id])

    def test_prefix_returning_multiple_matches(self) -> None:
        """A shared prefix returns all matching tasks."""
        result_ids = {t.id for t in self.index.find_by_title("Fix")}
        self.assertEqual(result_ids, {self.fix_login.id, self.fix_certs.id})

    def test_no_match_returns_empty_list(self) -> None:
        """An unmatched prefix returns an empty list."""
        self.assertEqual(self.index.find_by_title("Delete"), [])

    def test_matching_is_case_sensitive(self) -> None:
        """Lowercase prefix does not match a title-cased task."""
        self.assertEqual(self.index.find_by_title("fix"), [])

    def test_scoped_by_board(self) -> None:
        """board= restricts results to that board."""
        results = self.index.find_by_title("Fix", board="proj")
        self.assertEqual([t.id for t in results], [self.fix_login.id])

    def test_scoped_by_column(self) -> None:
        """column= restricts results to that column within the board."""
        results = self.index.find_by_title("Fix", board="proj", column="todo")
        self.assertEqual([t.id for t in results], [self.fix_login.id])

    def test_column_scope_excludes_other_columns(self) -> None:
        """A task in a different column is excluded when column= is given."""
        results = self.index.find_by_title("Add", board="proj", column="todo")
        self.assertEqual(results, [])


class TestKnownPaths(unittest.TestCase):
    """known_paths returns every indexed path, optionally scoped to a board."""

    def setUp(self) -> None:
        self.index = InMemoryIndex()
        self.a1 = make_task(title="Task one", board="alpha")
        self.a2 = make_task(title="Task two", board="alpha")
        self.b1 = make_task(title="Task three", board="beta")
        for t in (self.a1, self.a2, self.b1):
            self.index.upsert_task(t)

    def test_all_boards(self) -> None:
        """known_paths() with no argument returns paths from all boards."""
        self.assertEqual(self.index.known_paths(), {self.a1.path, self.a2.path, self.b1.path})

    def test_scoped_by_board(self) -> None:
        """known_paths(board=x) returns only paths in that board."""
        self.assertEqual(self.index.known_paths(board="alpha"), {self.a1.path, self.a2.path})

    def test_empty_index_returns_empty_set(self) -> None:
        """An empty index returns an empty set."""
        self.assertEqual(InMemoryIndex().known_paths(), set())
