"""Tests for picking a board in the switcher."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board_switcher import BoardSwitcherScreen
from kanban.tui.widgets import PrefixList

BOARDS = ["alpha", "beta", "gamma"]


def _make_service() -> KanbanService:
    """Return a service holding three boards, with alpha active."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    for slug in BOARDS:
        repo.create_board(slug.capitalize(), slug=Slug(slug))
        repo.create_column(Slug(slug), "todo", slug=Slug("todo"))

    svc.set_board(Slug("alpha"))
    return svc


async def _open_switcher(pilot: Pilot[None]) -> BoardSwitcherScreen:
    """Open the switcher and return it once it is on the stack."""
    await pilot.pause()
    await pilot.press("b")
    await pilot.pause()
    return next(
        s for s in pilot.app.screen_stack if isinstance(s, BoardSwitcherScreen)
    )


def _rows(screen: BoardSwitcherScreen) -> PrefixList:
    """Return the switcher's list of boards."""
    return screen.query_one("#board-list", PrefixList)


class TestBoardSwitcherRows(unittest.IsolatedAsyncioTestCase):
    """The rows describe each board, and end with the new-board option."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_rows_lead_with_the_name(self) -> None:
        """Every board row starts with the board's display name."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            rows = _rows(screen)

            for index, slug in enumerate(BOARDS):
                prompt = rows.get_option_at_index(index).prompt
                self.assertTrue(str(prompt).startswith(slug.capitalize()))

    async def test_rows_include_the_path(self) -> None:
        """The path follows the name."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            prompt = str(_rows(screen).get_option_at_index(0).prompt)

            self.assertIn("/alpha", prompt)

    async def test_keys_are_the_board_slugs(self) -> None:
        """Typing is matched against the board slugs, with the new-board row last."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)

            self.assertEqual(_rows(screen).keys[: len(BOARDS)], BOARDS)

    async def test_starts_on_the_active_board(self) -> None:
        """The list opens highlighting the board that is already active."""
        # The board the switcher highlights is the one the board screen loaded
        # with, so it is chosen before the app starts.
        svc = _make_service()
        svc.set_board(Slug("beta"))

        async with KanbanApp(svc).run_test() as pilot:
            screen = await _open_switcher(pilot)

            self.assertEqual(_rows(screen).highlighted, BOARDS.index("beta"))


class TestBoardSwitcherTypeAhead(unittest.IsolatedAsyncioTestCase):
    """Typing jumps to a board the way it does in the column prompt."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_typing_jumps_to_the_board(self) -> None:
        """A typed prefix highlights the first board whose slug starts with it."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("g")
            await pilot.pause()

            self.assertEqual(_rows(screen).highlighted, BOARDS.index("gamma"))

    async def test_typing_then_enter_switches_board(self) -> None:
        """Enter after typing switches to the board that was jumped to."""
        async with self.app.run_test() as pilot:
            await _open_switcher(pilot)
            await pilot.press("g")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(self.svc.working_board, "gamma")

    async def test_typing_does_not_reach_the_board_screen(self) -> None:
        """Letters the board binds are consumed by the list, not acted on beneath it."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("b")
            await pilot.pause()

            self.assertEqual(_rows(screen).highlighted, BOARDS.index("beta"))
            self.assertIs(pilot.app.screen, screen)

    async def test_typing_is_not_shown(self) -> None:
        """The switcher jumps without displaying the prefix being typed."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("g")
            await pilot.pause()

            self.assertFalse(_rows(screen).border_subtitle)

    async def test_unmatched_letter_leaves_the_highlight(self) -> None:
        """A letter no board starts with changes nothing."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("z")
            await pilot.pause()

            self.assertEqual(_rows(screen).highlighted, BOARDS.index("alpha"))


class TestBoardSwitcherChoice(unittest.IsolatedAsyncioTestCase):
    """Arrowing and cancelling behave as they did before type-ahead."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_arrowing_switches_board(self) -> None:
        """Down then enter switches to the next board in the list."""
        async with self.app.run_test() as pilot:
            await _open_switcher(pilot)
            await pilot.press("down", "enter")
            await pilot.pause()

            self.assertEqual(self.svc.working_board, "beta")

    async def test_escape_leaves_the_board_alone(self) -> None:
        """Cancelling the switcher keeps the active board."""
        async with self.app.run_test() as pilot:
            await _open_switcher(pilot)
            await pilot.press("down")
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(self.svc.working_board, "alpha")

    async def test_new_board_row_is_reachable_by_typing(self) -> None:
        """`+` jumps to the new-board option at the end of the list."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("plus")
            await pilot.pause()

            self.assertEqual(_rows(screen).highlighted, len(BOARDS))


if __name__ == "__main__":
    unittest.main()
