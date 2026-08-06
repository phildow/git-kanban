"""Tests for KanbanService context helpers: is_initialized, working_path, path_components,
set_board, and clear_user_context.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService
from kanban.storage.base import BoardNotFound
from kanban.storage.memory import InMemoryRepository


def _make_service() -> tuple[InMemoryRepository, KanbanService]:
    """Return a fresh in-memory repository and service pair."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )
    return repo, svc


class TestKanbanServiceIsInitialized(unittest.TestCase):
    """is_initialized reflects the repository's init state."""

    def test_is_initialized_false_before_init(self) -> None:
        """A fresh service reports is_initialized as False."""
        _, svc = _make_service()

        self.assertFalse(svc.is_initialized)

    def test_is_initialized_true_after_init(self) -> None:
        """After initialize_kanban the service reports is_initialized as True."""
        _, svc = _make_service()
        svc.initialize_kanban()

        self.assertTrue(svc.is_initialized)


class TestKanbanServiceWorkingPath(unittest.TestCase):
    """working_path reflects the active board as an absolute path."""

    def test_working_path_defaults_to_root(self) -> None:
        """With no active board, working_path is the root '/' path."""
        _, svc = _make_service()

        self.assertEqual(svc.working_path, Path("/"))

    def test_working_path_reflects_active_board(self) -> None:
        """Setting an active board makes working_path '/board'."""
        _, svc = _make_service()
        svc.update_user_context(board="alpha")

        self.assertEqual(svc.working_path, Path("/alpha"))


class TestKanbanServicePathComponents(unittest.TestCase):
    """path_components splits a board/column/task path into slugs."""

    def setUp(self) -> None:
        _, self.svc = _make_service()

    def test_path_components_none_returns_all_none(self) -> None:
        """path_components(None) returns (None, None, None) when there is no context."""
        board, column, task = self.svc.path_components()

        self.assertEqual((board, column, task), (None, None, None))

    def test_path_components_splits_absolute_path(self) -> None:
        """path_components parses '/board/column/task' into three slugs."""
        board, column, task = self.svc.path_components("/alpha/todo/fix-login")

        self.assertEqual(board, "alpha")
        self.assertEqual(column, "todo")
        self.assertEqual(task, "fix-login")

    def test_path_components_returns_none_for_missing_segments(self) -> None:
        """path_components fills unavailable segments with None."""
        board, column, task = self.svc.path_components("/alpha")

        self.assertEqual(board, "alpha")
        self.assertIsNone(column)
        self.assertIsNone(task)

    def test_path_components_uses_active_board_for_relative_paths(self) -> None:
        """Relative paths are resolved under the active board."""
        self.svc.update_user_context(board="alpha")

        board, column, task = self.svc.path_components("todo")

        self.assertEqual(board, "alpha")
        self.assertEqual(column, "todo")
        self.assertIsNone(task)

    def test_path_components_accepts_path_input(self) -> None:
        """path_components accepts a pathlib.Path in addition to str."""
        board, column, _ = self.svc.path_components(Path("/alpha/todo"))

        self.assertEqual(board, "alpha")
        self.assertEqual(column, "todo")


class TestKanbanServiceSetBoard(unittest.TestCase):
    """set_board validates the board exists before setting the active context."""

    def setUp(self) -> None:
        self.repo, self.svc = _make_service()
        self.repo.create_board("alpha", slug="alpha")

    def test_set_board_updates_working_board(self) -> None:
        """set_board makes working_board return the given slug."""
        self.svc.set_board("alpha")

        self.assertEqual(self.svc.working_board, "alpha")

    def test_set_board_returns_user_context(self) -> None:
        """set_board returns the updated UserContext."""
        ctx = self.svc.set_board("alpha")

        self.assertEqual(ctx.board, "alpha")

    def test_set_board_raises_for_missing_board(self) -> None:
        """set_board raises BoardNotFound when the slug does not exist."""
        with self.assertRaises(BoardNotFound):
            self.svc.set_board("missing")

    def test_set_board_persists_via_userdata(self) -> None:
        """set_board writes the active board to userdata."""
        self.svc.set_board("alpha")

        self.assertEqual(self.svc.get_userdata("user-context.board"), "alpha")


class TestKanbanServiceClearUserContext(unittest.TestCase):
    """clear_user_context resets the active board to None."""

    def setUp(self) -> None:
        self.repo, self.svc = _make_service()
        self.repo.create_board("alpha", slug="alpha")
        self.svc.set_board("alpha")

    def test_clear_user_context_removes_working_board(self) -> None:
        """After clear_user_context, working_board is None."""
        self.svc.clear_user_context()

        self.assertIsNone(self.svc.working_board)

    def test_clear_user_context_returns_empty_context(self) -> None:
        """clear_user_context returns the UserContext with board=None."""
        ctx = self.svc.clear_user_context()

        self.assertIsNone(ctx.board)

    def test_clear_user_context_clears_userdata(self) -> None:
        """clear_user_context removes the persisted board from userdata."""
        self.svc.clear_user_context()

        self.assertIsNone(self.svc.get_userdata("user-context.board"))


if __name__ == "__main__":
    unittest.main()
