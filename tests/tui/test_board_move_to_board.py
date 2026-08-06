"""Tests for sending a card to another board from move mode."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Input, Static
from textual.widgets._footer import FooterKey

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.screens.board_switcher import BoardSwitcherScreen
from kanban.tui.screens.confirm import ConfirmScreen
from kanban.tui.widgets import ColumnView, PrefixList


def _make_service(*, shared_column: bool = True) -> KanbanService:
    """
    Return a service holding two boards, `alpha` — the active one — and `beta`.

    `alpha` holds every task.  `beta` carries a `todo` of its own when
    `shared_column` is set, which is what a card moved to it should land in, and
    otherwise only columns `alpha` has no name in common with.
    """
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    repo.create_column("alpha", "doing", slug="doing")

    repo.create_board("beta", slug="beta")
    if shared_column:
        repo.create_column("beta", "todo", slug="todo")
    repo.create_column("beta", "shipped", slug="shipped")

    svc.set_board(Slug("alpha"))

    for title in ("first", "second"):
        svc.create_task("/alpha/todo", TaskCreateParams(title=title))

    return svc


async def _board_screen(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen once the app has pushed and loaded it."""
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


def _shown(screen: BoardScreen) -> dict[str, list[str]]:
    """Return the task slugs each column has cards mounted for, by column slug."""
    return {
        view.column.slug: [card.card_task.slug for card in view.cards]
        for view in screen.query(ColumnView)
    }


def _stored(svc: KanbanService, board: str) -> dict[str, list[str]]:
    """Return the task slugs each column of `board` holds in the store."""
    held: dict[str, list[str]] = {}
    for column in svc.get_columns(Path(f"/{board}")):
        tasks = svc.get_tasks(Path(f"/{board}/{column.slug}"))
        held[column.slug] = [task.slug for task in tasks]
    return held


def _footer_actions(screen: BoardScreen) -> set[str]:
    """Return the actions the footer is currently showing a key for."""
    return {key.action for key in screen.query(FooterKey)}


async def _open_list(pilot: Pilot[None]) -> BoardSwitcherScreen:
    """Stage the focused card for a move and open the board list on it."""
    await pilot.press("m")
    await pilot.press("b")
    await pilot.pause()
    return next(
        s for s in pilot.app.screen_stack if isinstance(s, BoardSwitcherScreen)
    )


def _editing(screen: BoardSwitcherScreen) -> bool:
    """Return whether the naming field is showing."""
    return screen.query_one("#board-name", Input).has_class("-visible")


async def _pick_beta(pilot: Pilot[None]) -> None:
    """Open the board list from move mode and choose `beta`, the second board."""
    await pilot.press("b")
    await pilot.pause()
    await pilot.press("down", "enter")
    await pilot.pause()


class TestMoveToBoardWithSameColumn(unittest.IsolatedAsyncioTestCase):
    """A card sent to a board with the same column lands in that column."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_card_lands_in_the_column_of_the_same_name(self) -> None:
        """The card is in the destination board's `todo`."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("m")
            await _pick_beta(pilot)

            self.assertEqual(_stored(self.svc, "beta")["todo"], ["first"])

    async def test_card_leaves_the_source_board(self) -> None:
        """The column the card was in no longer holds it."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("m")
            await _pick_beta(pilot)

            self.assertEqual(_stored(self.svc, "alpha")["todo"], ["second"])

    async def test_board_on_screen_does_not_change(self) -> None:
        """The user is left on the board they were already on."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await _pick_beta(pilot)

            self.assertEqual(self.svc.working_board, "alpha")
            self.assertEqual(_shown(screen), _stored(self.svc, "alpha"))

    async def test_move_mode_ends(self) -> None:
        """Choosing a board commits the move, so the mode is over."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await _pick_beta(pilot)

            self.assertFalse(screen.move_mode)


class TestMoveToBoardWithoutSameColumn(unittest.IsolatedAsyncioTestCase):
    """A card sent to a board with no column of that name lands in the first one."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service(shared_column=False)
        self.app = KanbanApp(self.svc)

    async def test_card_lands_in_the_first_column(self) -> None:
        """The card is in the destination board's leftmost column."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("m")
            await _pick_beta(pilot)

            self.assertEqual(_stored(self.svc, "beta")["shipped"], ["first"])


class TestMoveToBoardStagedElsewhere(unittest.IsolatedAsyncioTestCase):
    """A card staged in another column first still leaves the board cleanly."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_staged_column_is_redrawn(self) -> None:
        """The column that was previewing the card no longer draws it."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("right")  # preview it in doing
            await pilot.pause()
            await _pick_beta(pilot)

            self.assertEqual(_shown(screen), _stored(self.svc, "alpha"))


class TestBoardListCancelled(unittest.IsolatedAsyncioTestCase):
    """Closing the board list leaves the move where it was."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_escape_keeps_move_mode(self) -> None:
        """Escape closes the list and the card stays staged."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("b")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(
                any(isinstance(s, BoardSwitcherScreen) for s in pilot.app.screen_stack)
            )
            self.assertTrue(screen.move_mode)

    async def test_escape_writes_nothing(self) -> None:
        """Nothing was moved while the list was up."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("b")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(_stored(self.svc, "alpha")["todo"], ["first", "second"])
            self.assertEqual(_stored(self.svc, "beta")["todo"], [])


class TestBoardListManagesNothing(unittest.IsolatedAsyncioTestCase):
    """Mid-move the board list is a question: only a board and esc answer it."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_only_boards_are_listed(self) -> None:
        """The row that creates a board is not offered."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)
            screen = await _open_list(pilot)

            self.assertEqual(screen.query_one(PrefixList).keys, ["alpha", "beta"])

    async def test_new_does_not_open_a_field(self) -> None:
        """`N` names nothing."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)
            screen = await _open_list(pilot)

            await pilot.press("N")
            await pilot.pause()

            self.assertFalse(_editing(screen))
            self.assertEqual([board.slug for board in self.svc.get_boards()],
                             ["alpha", "beta"])

    async def test_rename_does_not_open_a_field(self) -> None:
        """`R` renames nothing."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)
            screen = await _open_list(pilot)

            await pilot.press("R")
            await pilot.pause()

            self.assertFalse(_editing(screen))
            self.assertEqual([board.name for board in self.svc.get_boards()],
                             ["alpha", "beta"])

    async def test_delete_does_not_ask(self) -> None:
        """`D` puts up no confirmation, so nothing can be deleted."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)
            await _open_list(pilot)

            await pilot.press("D")
            await pilot.pause()

            self.assertFalse(
                any(isinstance(s, ConfirmScreen) for s in pilot.app.screen_stack)
            )
            self.assertEqual([board.slug for board in self.svc.get_boards()],
                             ["alpha", "beta"])

    async def test_hints_offer_only_the_two_answers(self) -> None:
        """The hints name choosing and closing, and no management key."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)
            screen = await _open_list(pilot)

            hints = str(screen.query_one("#board-hint", Static).visual)

            self.assertIn("Choose", hints)
            self.assertIn("Close", hints)
            for label in ("New", "Rename", "Delete"):
                self.assertNotIn(label, hints)

    async def test_the_card_still_moves(self) -> None:
        """Choosing a board is still an answer, management or not."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)
            await _open_list(pilot)

            await pilot.press("down", "enter")
            await pilot.pause()

            self.assertEqual(_stored(self.svc, "beta")["todo"], ["first"])


class TestFooterAfterBoardList(unittest.IsolatedAsyncioTestCase):
    """The key hints follow the mode back out of the board list."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_hints_return_to_the_card_actions(self) -> None:
        """
        Leaving the list and then the move restores the board's own keys.

        The list hands the focus back with the card still staged, which
        recomposes the footer against the move-mode keys; ending the move has to
        recompose it again or the hints stay on a mode that is over.
        """
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("b")
            await pilot.pause()
            await pilot.press("escape")  # close the list, move still staged
            await pilot.pause()
            await pilot.press("escape")  # end the move
            await pilot.pause()

            self.assertFalse(screen.move_mode)
            self.assertIn("new_task", _footer_actions(screen))

    async def test_hints_drop_the_card_actions_while_staged(self) -> None:
        """A card still staged after the list closes keeps the move-mode keys."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("b")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertTrue(screen.move_mode)
            self.assertNotIn("new_task", _footer_actions(screen))


class TestMoveToCurrentBoard(unittest.IsolatedAsyncioTestCase):
    """Choosing the board the card is already on leaves the move staged."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_move_mode_survives(self) -> None:
        """The card is already here, so there is nothing to write and nothing to end."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("m")
            await pilot.press("b")
            await pilot.pause()
            await pilot.press("enter")  # alpha, the highlighted board
            await pilot.pause()

            self.assertTrue(screen.move_mode)
            self.assertEqual(_stored(self.svc, "alpha")["todo"], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
