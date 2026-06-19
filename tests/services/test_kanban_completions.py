"""Behavior tests for `KanbanService.completions()`"""

from __future__ import annotations

import sys
import tempfile
import unittest

from pathlib import Path

from models import UserContext
from storage.kanban import BoardNotFound, ColumnNotFound
from services.kanban import KanbanService, TaskCreateParams
from services.git import GitService
from services.index import IndexService
from storage.memory import InMemoryRepository

class TestKanbanServiceCompletions(unittest.TestCase):
    def setUp(self) -> None:
        temp_dir = tempfile.gettempdir()
        self.repo = InMemoryRepository(root=Path(temp_dir))
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
            user_context=UserContext(),
        )
        self.svc.create_board("alpha")
        self.svc.create_board("beta")

        """
        /alpha/
            /todo/
            /in-progress/
            /in-review/
            /done/
        /beta/
            /todo/
            /in-progress/
            /in-review/
            /done/
        """

    def test_completions_for_root(self):
        completions = self.svc.completions_for_path("/")
        expected_completions = ["alpha/", "beta/"]

        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)

    def test_completions_for_partial_board(self):
        completions = self.svc.completions_for_path("/alp")
        expected_completions = ["alpha/"]

        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)

    def test_completions_for_board(self):
        completions = self.svc.completions_for_path("/alpha/")
        expected_completions = ["todo/", "in-progress/", "in-review/", "done/"]

        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)

    def test_completions_for_partial_column(self):
        completions = self.svc.completions_for_path("/alpha/to/")
        expected_completions = ["todo/"]

        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)

    def test_completions_for_column(self):
        completions = self.svc.completions_for_path("/alpha/todo/")
        expected_completions = [] # no tasks yet
        
        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)

    def test_completions_for_task_prefix_returns_slugs_not_titles(self):
        self.svc.create_task("alpha/todo/Fix Parser", TaskCreateParams())
        self.svc.create_task("alpha/todo/Fix Tests", TaskCreateParams())

        completions = self.svc.completions_for_path("/alpha/todo/Fix")

        self.assertCountEqual(completions, ["fix-parser", "fix-tests"])
        self.assertNotIn("Fix Parser", completions)
        self.assertNotIn("Fix Tests", completions)

    def test_completions_for_nonexistent_board(self):
        completions = self.svc.completions_for_path("/missing/")
        expected_completions = []

        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)

    def test_completions_for_nonexistent_column(self):
        completions = self.svc.completions_for_path("/alpha/missing/")
        expected_completions = []

        self.assertCountEqual(completions, expected_completions)
        for completion in expected_completions:
            self.assertIn(completion, completions)
