"""Tests for picking a board in the switcher, and for managing boards there."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Input, Static

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board_switcher import (
    BoardChoice,
    BoardsChanged,
    BoardSwitcherScreen,
    SwitchToBoard,
)
from kanban.tui.screens.confirm import ConfirmScreen
from kanban.tui.widgets import PrefixList

BOARDS = ["alpha", "beta", "gamma"]


def _make_service(*, boards: list[str] = BOARDS, active: str | None = "alpha") -> KanbanService:
    """Return a service holding `boards`, with `active` set as the working board."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    for slug in boards:
        repo.create_board(slug.capitalize(), slug=Slug(slug))
        repo.create_column(Slug(slug), "todo", slug=Slug("todo"))

    if active is not None:
        svc.set_board(Slug(active))
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


def _field(screen: BoardSwitcherScreen) -> Input:
    """Return the field a board is named in."""
    return screen.query_one("#board-name", Input)


def _editing(screen: BoardSwitcherScreen) -> bool:
    """Return whether the naming field is showing."""
    return _field(screen).has_class("-visible")


def _hints(screen: BoardSwitcherScreen) -> str:
    """Return the key hints shown at the bottom of the modal, as plain text."""
    return str(screen.query_one("#board-hint", Static).visual)


async def _type(pilot: Pilot[None], text: str) -> None:
    """
    Type `text` a character at a time into whatever has focus.

    Every simulated keypress costs Textual a round trip of the screen's message
    queue — tens of milliseconds at best, and occasionally close to a second —
    so this is kept for the one test that is about typing.  Tests that only
    need a name in the field set `.value` and submit it.
    """
    for character in text:
        await pilot.press(character)
    await pilot.pause()


async def _name(pilot: Pilot[None], screen: BoardSwitcherScreen, name: str) -> None:
    """Put `name` in the open field and submit it."""
    _field(screen).value = name
    await pilot.press("enter")
    await pilot.pause()


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


class TestBoardSwitcherOnStartup(unittest.IsolatedAsyncioTestCase):
    """With no working board the app opens on the switcher."""

    async def test_switcher_opens_without_a_working_board(self) -> None:
        """The switcher is on screen as soon as the board has loaded."""
        app = KanbanApp(_make_service(active=None))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, BoardSwitcherScreen)

    async def test_choosing_sets_the_working_board(self) -> None:
        """Picking from the startup switcher sets the board that was missing."""
        svc = _make_service(active=None)

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("g")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(svc.working_board, "gamma")

    async def test_switcher_stays_closed_with_a_working_board(self) -> None:
        """An active board is shown directly, without asking."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            self.assertNotIsInstance(pilot.app.screen, BoardSwitcherScreen)

    async def test_switcher_stays_closed_without_any_boards(self) -> None:
        """With nothing to choose between, the empty board screen stands."""
        app = KanbanApp(_make_service(boards=[], active=None))

        async with app.run_test() as pilot:
            await pilot.pause()

            self.assertNotIsInstance(pilot.app.screen, BoardSwitcherScreen)


class TestBoardSwitcherHints(unittest.IsolatedAsyncioTestCase):
    """The management keys are named at the bottom of the modal."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_hints_name_every_management_key(self) -> None:
        """The switcher opens showing what it answers to."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            hints = _hints(screen)

            for description in ("Switch", "New", "Rename", "Delete", "Close"):
                self.assertIn(description, hints)

    async def test_hints_change_while_naming(self) -> None:
        """Naming a board swaps the hints for the ones that apply to the field."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            self.assertIn("Save", _hints(screen))
            self.assertNotIn("Delete", _hints(screen))

    async def test_hints_come_back_when_the_field_closes(self) -> None:
        """Cancelling the field restores the management hints."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.press("escape")
            await pilot.pause()

            self.assertIn("Rename", _hints(screen))


class TestBoardSwitcherTypeAheadWithManagementKeys(unittest.IsolatedAsyncioTestCase):
    """The shifted management keys leave every lowercase letter to type-ahead."""

    # Boards named after the letters the management keys would otherwise take.
    BOARDS = ["notes", "done", "roadmap"]

    async def _jumps(self, letter: str, slug: str) -> None:
        """Assert that `letter` highlights the board `slug` and manages nothing."""
        # A fresh app per letter: typed prefixes accumulate for a second, so two
        # letters pressed in a row would be read as one search.
        svc = _make_service(boards=self.BOARDS, active="notes")

        async with KanbanApp(svc).run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press(letter)
            await pilot.pause()

            self.assertEqual(_rows(screen).highlighted, self.BOARDS.index(slug))
            self.assertFalse(_editing(screen))

    async def test_r_jumps_rather_than_renaming(self) -> None:
        """Lowercase `r` reaches a board called `roadmap`."""
        await self._jumps("r", "roadmap")

    async def test_d_jumps_rather_than_deleting(self) -> None:
        """Lowercase `d` reaches a board called `done`."""
        await self._jumps("d", "done")

    async def test_n_jumps_rather_than_creating(self) -> None:
        """Lowercase `n` reaches a board called `notes`."""
        await self._jumps("n", "notes")


class TestBoardSwitcherRename(unittest.IsolatedAsyncioTestCase):
    """`R` renames the highlighted board on its own row."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_field_opens_on_the_current_name(self) -> None:
        """The field is prefilled with the name being changed."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("down", "R")
            await pilot.pause()

            self.assertTrue(_editing(screen))
            self.assertEqual(_field(screen).value, "Beta")

    async def test_field_covers_the_highlighted_row(self) -> None:
        """The field is laid over the row it is naming, not beside or below it."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("down", "R")
            await pilot.pause()

            rows = _rows(screen)
            content = rows.scrollable_content_region
            field = _field(screen).region

            self.assertEqual(field.x, content.x)
            self.assertEqual(field.width, content.width)
            self.assertEqual(field.y, content.y + 1)
            self.assertEqual(field.height, 1)

    async def test_typing_reaches_the_field(self) -> None:
        """Keystrokes land in the field rather than in the list behind it."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            _field(screen).value = ""
            await _type(pilot, "zed")

            self.assertEqual(_field(screen).value, "zed")
            self.assertEqual(_rows(screen).highlighted, 0)

    async def test_enter_renames_the_board(self) -> None:
        """Submitting the field renames the board through the service."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            await _name(pilot, screen, "Alpine")

            slugs = [board.slug for board in self.svc.get_boards()]
            self.assertIn("alpine", slugs)
            self.assertNotIn("alpha", slugs)

    async def test_the_list_stays_open_on_the_renamed_board(self) -> None:
        """The switcher stays up, highlighting the board under its new slug."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            await _name(pilot, screen, "Zulu")

            rows = _rows(screen)
            self.assertIs(pilot.app.screen, screen)
            self.assertFalse(_editing(screen))
            self.assertEqual(rows.keys[rows.highlighted or 0], "zulu")

    async def test_escape_cancels_the_rename(self) -> None:
        """Escape closes the field and leaves the board named as it was."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            _field(screen).value = "Alpine"
            await pilot.press("escape")
            await pilot.pause()

            self.assertIs(pilot.app.screen, screen)
            self.assertFalse(_editing(screen))
            self.assertIn("alpha", [board.slug for board in self.svc.get_boards()])

    async def test_an_empty_name_cancels(self) -> None:
        """Submitting nothing is the same as cancelling."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            _field(screen).value = "   "
            await pilot.press("enter")
            await pilot.pause()

            self.assertFalse(_editing(screen))
            self.assertIn("alpha", [board.slug for board in self.svc.get_boards()])

    async def test_a_refused_name_leaves_the_field_open(self) -> None:
        """A name already taken is reported, and stays in the field to be corrected."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("R")
            await pilot.pause()

            _field(screen).value = "Beta"
            await pilot.press("enter")
            await pilot.pause()

            self.assertTrue(_editing(screen))
            self.assertEqual(_field(screen).value, "Beta")
            self.assertIn("alpha", [board.slug for board in self.svc.get_boards()])

    async def test_the_new_board_row_cannot_be_renamed(self) -> None:
        """`R` on the new-board option does nothing."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("plus", "R")
            await pilot.pause()

            self.assertFalse(_editing(screen))


class TestBoardSwitcherCreate(unittest.IsolatedAsyncioTestCase):
    """`N` names a new board in a row appended to the list."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_a_draft_row_is_appended(self) -> None:
        """A blank row goes on the end, below the new-board option, and is edited."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("N")
            await pilot.pause()

            rows = _rows(screen)
            self.assertEqual(len(rows.keys), len(BOARDS) + 2)
            self.assertEqual(rows.highlighted, len(BOARDS) + 1)
            self.assertTrue(_editing(screen))
            self.assertEqual(_field(screen).value, "")

    async def test_the_new_board_row_starts_the_same_draft(self) -> None:
        """Enter on the new-board option opens the same field."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("plus", "enter")
            await pilot.pause()

            self.assertTrue(_editing(screen))
            self.assertEqual(_rows(screen).highlighted, len(BOARDS) + 1)

    async def test_enter_creates_the_board(self) -> None:
        """The named board is created with the default columns."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("N")
            await pilot.pause()

            await _name(pilot, screen, "delta")

            slugs = [board.slug for board in self.svc.get_boards()]
            self.assertIn("delta", slugs)
            columns = self.svc.get_columns(Path("/delta"))
            self.assertEqual([column.slug for column in columns][0], "todo")

    async def test_creating_stays_in_the_switcher(self) -> None:
        """The board is not switched to: the list stays up, highlighting it."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("N")
            await pilot.pause()

            await _name(pilot, screen, "delta")

            rows = _rows(screen)
            self.assertIs(pilot.app.screen, screen)
            self.assertFalse(_editing(screen))
            self.assertEqual(rows.keys[rows.highlighted or 0], "delta")
            self.assertEqual(self.svc.working_board, "alpha")

    async def test_escape_drops_the_draft_row(self) -> None:
        """Cancelling removes the appended row and creates nothing."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("N")
            await pilot.pause()

            _field(screen).value = "delta"
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(len(_rows(screen).keys), len(BOARDS) + 1)
            self.assertEqual([b.slug for b in self.svc.get_boards()], BOARDS)


class TestBoardSwitcherDelete(unittest.IsolatedAsyncioTestCase):
    """`D` deletes the highlighted board, once confirmed."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_delete_asks_first(self) -> None:
        """A confirmation modal names the board before anything is written."""
        async with self.app.run_test() as pilot:
            await _open_switcher(pilot)
            await pilot.press("D")
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, ConfirmScreen)
            self.assertEqual([b.slug for b in self.svc.get_boards()], BOARDS)

    async def test_confirming_deletes_the_board(self) -> None:
        """Confirming removes the board and its row."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("D")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            self.assertEqual([b.slug for b in self.svc.get_boards()], BOARDS[1:])
            self.assertEqual(_rows(screen).keys, [*BOARDS[1:], "+"])

    async def test_the_highlight_lands_on_the_next_board(self) -> None:
        """The row the deleted board left is taken by the one below it."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("down", "D")
            await pilot.pause()
            await pilot.press("y")
            await pilot.pause()

            rows = _rows(screen)
            self.assertEqual(rows.keys[rows.highlighted or 0], "gamma")

    async def test_cancelling_keeps_the_board(self) -> None:
        """Declining the confirmation writes nothing."""
        async with self.app.run_test() as pilot:
            await _open_switcher(pilot)
            await pilot.press("D")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual([b.slug for b in self.svc.get_boards()], BOARDS)

    async def test_the_new_board_row_cannot_be_deleted(self) -> None:
        """`D` on the new-board option asks nothing."""
        async with self.app.run_test() as pilot:
            screen = await _open_switcher(pilot)
            await pilot.press("plus", "D")
            await pilot.pause()

            self.assertIs(pilot.app.screen, screen)


class TestBoardSwitcherResult(unittest.IsolatedAsyncioTestCase):
    """What the switcher dismisses with tells the board screen whether to reload."""

    async def _dismissal(self, svc: KanbanService, keys: list[str]) -> BoardChoice | None:
        """Open a switcher over `svc`, press `keys`, and return what it came back with."""
        results: list[BoardChoice | None] = []

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            pilot.app.push_screen(BoardSwitcherScreen(svc), results.append)
            await pilot.pause()

            for key in keys:
                await pilot.press(key)
                await pilot.pause()

        return results[0] if results else None

    async def test_cancelling_an_untouched_list_reports_nothing(self) -> None:
        """Escape with nothing done dismisses with None, so the board is left alone."""
        result = await self._dismissal(_make_service(), ["escape"])

        self.assertIsNone(result)

    async def test_cancelling_after_a_change_reports_it(self) -> None:
        """Escape after a delete asks the board screen to reload."""
        result = await self._dismissal(_make_service(), ["D", "y", "escape"])

        self.assertIsInstance(result, BoardsChanged)

    async def test_choosing_a_board_reports_it(self) -> None:
        """Enter on a board dismisses with the board to switch to."""
        result = await self._dismissal(_make_service(), ["enter"])

        self.assertEqual(result, SwitchToBoard(Slug("alpha")))


if __name__ == "__main__":
    unittest.main()
