"""Behavior tests for `KanbanService.completions()`"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from models import UserContext
from storage.kanban_repository import BoardNotFound, ColumnNotFound
from services.kanban_service import KanbanService
from services.git_service import GitService
from services.index_service import IndexService
from storage.memory_repository import InMemoryRepository

class TestKanbanServiceCompletions(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = InMemoryRepository()
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
            user_context=UserContext(),
        )
        self.svc.create_board("alpha")
        self.svc.create_column("alpha/todo")
        self.svc.create_column("alpha/done")
        self.svc.create_board("beta")
        self.svc.create_column("beta/backlog")

        """
        /alpha/
            /todo/
            /done/
        /beta/
            /backlog/
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
        expected_completions = ["todo/", "done/"]
        
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
