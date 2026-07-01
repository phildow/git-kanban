"""Tests for KanbanService.assign_task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceAssignTask(unittest.TestCase):
    """KanbanService.assign_task sets assigned_to and returns the updated Task."""

    def setUp(self) -> None:
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=GitService(),
        )
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")
        self.svc.create_task("alpha/todo/fix-login", TaskCreateParams())

    def test_returns_task_with_new_assigned_to(self) -> None:
        """assign_task returns a Task whose assigned_to matches the given user."""
        result = self.svc.assign_task("alpha/todo/fix-login", "alice")
        self.assertEqual(result.assigned_to, "alice")

    def test_overwrites_existing_assigned_to(self) -> None:
        """assign_task replaces a previously set assigned_to value."""
        self.svc.assign_task("alpha/todo/fix-login", "alice")
        result = self.svc.assign_task("alpha/todo/fix-login", "bob")
        self.assertEqual(result.assigned_to, "bob")

    def test_returned_task_identity_matches_original(self) -> None:
        """assign_task returns the same task (by id) that was passed in."""
        original = self.svc.get_task("alpha/todo/fix-login")
        result = self.svc.assign_task("alpha/todo/fix-login", "alice")
        self.assertEqual(result.id, original.id)


if __name__ == "__main__":
    unittest.main()
