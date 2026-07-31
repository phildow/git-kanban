"""Tests for moving a card on the board screen."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.widgets import ColumnView


def _make_service() -> KanbanService:
    """Return a service holding one board with three columns, two of them populated."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    repo.create_column("alpha", "doing", slug="doing")
    repo.create_column("alpha", "done", slug="done")
    svc.set_board(Slug("alpha"))

    for title in ("first", "second", "third"):
        svc.create_task("/alpha/todo", TaskCreateParams(title=title))
    for title in ("fourth", "fifth"):
        svc.create_task("/alpha/doing", TaskCreateParams(title=title))

    return svc


async def _board_screen(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen once the app has pushed and loaded it."""
    await pilot.pause()
    # The board is pushed over the app's default screen, so it is reached
    # through the stack rather than by querying the app.
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


def _shown(screen: BoardScreen) -> dict[str, list[str]]:
    """Return the task slugs each column has cards mounted for, by column slug."""
    return {
        view.column.slug: [card.card_task.slug for card in view.cards]
        for view in screen.query(ColumnView)
    }


def _stored(svc: KanbanService) -> dict[str, list[str]]:
    """Return the task slugs each column holds in the store, by column slug."""
    shown: dict[str, list[str]] = {}
    for column in svc.get_columns(Slug("alpha")):
        tasks = svc.get_tasks(Path(f"/alpha/{column.slug}"))
        shown[column.slug] = [task.slug for task in tasks]
    return shown


class TestMoveToNamedColumn(unittest.IsolatedAsyncioTestCase):
    """Choosing a destination by name leaves the board showing what the store holds."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_board_matches_store_after_move(self) -> None:
        """Every column shows exactly the tasks it holds — no strays, no duplicates."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")  # stage the first card in todo
            await pilot.press("tab")  # ask for a destination by name
            await pilot.pause()
            await pilot.press("down", "down", "enter")  # pick "done"
            await pilot.pause()

            self.assertFalse(screen.move_mode)
            self.assertEqual(_shown(screen), _stored(self.svc))

    async def test_card_lands_in_the_named_column(self) -> None:
        """The staged card is in the column that was named, and only there."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("tab")
            await pilot.pause()
            await pilot.press("down", "down", "enter")
            await pilot.pause()

            shown = _shown(screen)
            self.assertIn("first", shown["done"])
            self.assertNotIn("first", shown["todo"])


class TestMoveStagedThenNamed(unittest.IsolatedAsyncioTestCase):
    """Naming a column after staging elsewhere clears the column it was staged in."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_staged_column_is_redrawn(self) -> None:
        """The column the card was previewed in no longer draws it."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")  # stage the first card in todo
            await pilot.press("right")  # preview it in doing
            await pilot.pause()
            await pilot.press("tab")  # then name done instead
            await pilot.pause()
            await pilot.press("down", "down", "enter")
            await pilot.pause()

            self.assertEqual(_shown(screen), _stored(self.svc))


class TestMoveCommittedWhileStaging(unittest.IsolatedAsyncioTestCase):
    """Committing before the staged preview has finished drawing."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_board_matches_store_after_move(self) -> None:
        """The refresh that follows the commit is the last word on every column."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            # No pause between staging and committing: the preview redraw is
            # still in flight when the commit schedules its own.
            await pilot.press("m", "right", "enter")
            await pilot.pause()

            self.assertEqual(_shown(screen), _stored(self.svc))


if __name__ == "__main__":
    unittest.main()
