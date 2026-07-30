"""Tests for KanbanService index-backed lookups: get_tags and get_assigned_tos."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.index.memory import InMemoryIndex
from kanban.models import Priority
from kanban.services.git import GitService
from kanban.services.index import IndexService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceGetTags(unittest.TestCase):
    """get_tags returns distinct tag values across indexed tasks."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=MagicMock(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_board("beta", slug="beta")
        self.repo.create_column("beta", "todo", slug="todo")

    def test_get_tags_returns_empty_when_no_tasks(self) -> None:
        """get_tags returns [] when no tasks have been created."""
        self.assertEqual(self.svc.get_tags(), [])

    def test_get_tags_returns_distinct_tags(self) -> None:
        """get_tags collects distinct tags across all indexed tasks."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login", tags=["bug", "auth"]))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="write-docs", tags=["docs", "bug"]))

        tags = self.svc.get_tags()

        self.assertEqual(set(tags), {"bug", "auth", "docs"})

    def test_get_tags_scoped_to_board(self) -> None:
        """get_tags with a board argument only returns tags from that board."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="a", tags=["alpha-only"]))
        self.svc.create_task("beta/todo", TaskCreateParams(title="b", tags=["beta-only"]))

        tags = self.svc.get_tags(board="alpha")

        self.assertEqual(set(tags), {"alpha-only"})


class TestKanbanServiceGetAssignedTos(unittest.TestCase):
    """get_assigned_tos returns distinct assigned_to values across indexed tasks."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(index_base=InMemoryIndex(), repository=self.repo),
            git_service=MagicMock(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.repo.create_board("beta", slug="beta")
        self.repo.create_column("beta", "todo", slug="todo")

    def test_get_assigned_tos_returns_empty_when_no_tasks(self) -> None:
        """get_assigned_tos returns [] when no tasks have been created."""
        self.assertEqual(self.svc.get_assigned_tos(), [])

    def test_get_assigned_tos_returns_distinct_names(self) -> None:
        """get_assigned_tos collects distinct assigned_to values."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="a", assigned_to="alice", priority=Priority.HIGH))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="b", assigned_to="bob"))
        self.svc.create_task("alpha/todo", TaskCreateParams(title="c", assigned_to="alice"))

        names = self.svc.get_assigned_tos()

        self.assertEqual(set(names), {"alice", "bob"})

    def test_get_assigned_tos_scoped_to_board(self) -> None:
        """get_assigned_tos with a board argument only returns names from that board."""
        self.svc.create_task("alpha/todo", TaskCreateParams(title="a", assigned_to="alice"))
        self.svc.create_task("beta/todo", TaskCreateParams(title="b", assigned_to="bob"))

        names = self.svc.get_assigned_tos(board="alpha")

        self.assertEqual(set(names), {"alice"})


if __name__ == "__main__":
    unittest.main()
