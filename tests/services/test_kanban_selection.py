"""Tests for KanbanService's selection: the screen state commands can act on."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository


def _make_service() -> KanbanService:
    """Return a service over an empty in-memory repository."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    return KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )


class TestKanbanServiceSelection(unittest.TestCase):
    """The selection is held for the session and set only by a consumer with one."""

    def setUp(self) -> None:
        self.svc = _make_service()

    def test_nothing_is_selected_to_begin_with(self) -> None:
        """A service starts with an empty selection, as the CLI and REPL leave it."""
        self.assertTrue(self.svc.selection.is_empty)

    def test_set_selection_records_every_part(self) -> None:
        """The board, column, and task are recorded together."""
        self.svc.set_selection(Slug("alpha"), Slug("todo"), Slug("fix-login"))

        self.assertEqual(self.svc.selection.board, "alpha")
        self.assertEqual(self.svc.selection.column, "todo")
        self.assertEqual(self.svc.selection.task, "fix-login")

    def test_set_selection_replaces_the_previous_one(self) -> None:
        """Setting a selection with no task drops the task previously selected."""
        self.svc.set_selection(Slug("alpha"), Slug("todo"), Slug("fix-login"))
        self.svc.set_selection(Slug("alpha"), Slug("done"))

        self.assertEqual(self.svc.selection.column, "done")
        self.assertIsNone(self.svc.selection.task)

    def test_clear_selection_empties_it(self) -> None:
        """Clearing leaves nothing selected."""
        self.svc.set_selection(Slug("alpha"), Slug("todo"), Slug("fix-login"))
        self.svc.clear_selection()

        self.assertTrue(self.svc.selection.is_empty)

    def test_selection_is_not_written_to_userdata(self) -> None:
        """A selection is live screen state; only the working board is persisted."""
        self.svc.set_selection(Slug("alpha"), Slug("todo"), Slug("fix-login"))

        reread = KanbanService(
            repository=self.svc.repository,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.svc.repository),
        )
        self.assertTrue(reread.selection.is_empty)


if __name__ == "__main__":
    unittest.main()
