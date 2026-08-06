"""Tests for the focusable column header on the board screen."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Static

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.screens.confirm import ConfirmScreen
from kanban.tui.widgets import ColumnHeader, ColumnPanel, ColumnView


def _make_service() -> KanbanService:
    """Return a service holding one board with three columns, one of them populated."""
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
    repo.create_column("alpha", "done", slug="done")
    svc.set_board(Slug("alpha"))

    for title in ("first", "second"):
        svc.create_task("/alpha/todo", TaskCreateParams(title=title))

    return svc


async def _board_screen(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen once the app has pushed and loaded it."""
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


def _columns(svc: KanbanService) -> list[str]:
    """Return the board's column slugs, in the order the store holds them."""
    return [column.slug for column in svc.get_columns(Slug("alpha"))]


def _headers(screen: BoardScreen) -> list[ColumnHeader]:
    """Return the mounted column headers, left to right."""
    return [panel.header for panel in screen.query(ColumnPanel)]


class TestFocusingTheHeader(unittest.IsolatedAsyncioTestCase):
    """`c` reaches the header from the cards below it, and it hands focus back; tab does not."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_c_focuses_the_header_of_the_selected_column(self) -> None:
        """`c` leaves the cards for the header above them."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _headers(screen)[0])

    async def test_up_stays_in_the_cards(self) -> None:
        """↑ at the top card stops there rather than walking out of the column."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("up", "up")
            await pilot.pause()

            self.assertIs(pilot.app.focused, screen.column_views[0])
            self.assertEqual(screen.column_views[0].index, 0)

    async def test_escape_returns_focus_to_the_cards(self) -> None:
        """esc on the header drops back into the column's card list."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "escape")
            await pilot.pause()

            self.assertIsInstance(pilot.app.focused, ColumnView)
            self.assertIs(pilot.app.focused, screen.column_views[0])

    async def test_c_returns_focus_to_the_cards(self) -> None:
        """`c` on the header drops back into the column's card list, as it entered."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "c")
            await pilot.pause()

            self.assertIsInstance(pilot.app.focused, ColumnView)
            self.assertIs(pilot.app.focused, screen.column_views[0])

    async def test_j_leaves_the_header_focused(self) -> None:
        """`j` is not the header's: `c` is the one way back to the cards."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "j")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _headers(screen)[0])

    async def test_down_leaves_the_header_focused(self) -> None:
        """↓ is not the header's: the arrow keys move along the strip, not off it."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "down")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _headers(screen)[0])

    async def test_right_moves_along_the_header_strip(self) -> None:
        """→ on a header focuses the next column's header, not its cards."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "right")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _headers(screen)[1])

    async def test_tab_skips_the_header_strip(self) -> None:
        """Tab from a column's cards moves straight on to the next column's."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("tab")
            await pilot.pause()

            self.assertIs(pilot.app.focused, screen.column_views[1])

    async def test_tab_from_a_header_stays_on_the_strip(self) -> None:
        """A focused header is the mode: tab moves along the strip, header to header."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "tab")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _headers(screen)[1])

    async def test_shift_tab_reverses_the_cycle(self) -> None:
        """Shift+Tab undoes a Tab."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("tab", "shift+tab")
            await pilot.pause()

            self.assertIs(pilot.app.focused, screen.column_views[0])

    async def test_c_focuses_the_header_of_an_empty_column(self) -> None:
        """A column with no cards still reaches its header."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("right")  # doing, which holds nothing
            await pilot.press("c")
            await pilot.pause()

            self.assertIs(pilot.app.focused, _headers(screen)[1])


class TestRenamingAColumn(unittest.IsolatedAsyncioTestCase):
    """`r` renames the column in a field that replaces its label."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_field_opens_on_the_current_name(self) -> None:
        """The field is prefilled with the name being changed."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "r")
            await pilot.pause()

            header = _headers(screen)[0]
            self.assertTrue(header.naming)
            self.assertEqual(header.field.value, "todo")

    async def test_submitting_renames_the_column(self) -> None:
        """The name typed reaches the store, under a slug of its own."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("c", "r")
            await pilot.pause()
            await pilot.press("end", "ctrl+u")
            await pilot.press(*"Up Next")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["up-next", "doing", "done"])

    async def test_renamed_column_keeps_its_tasks(self) -> None:
        """The cards move with the column and are drawn under the new name."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "r")
            await pilot.pause()
            await pilot.press("end", "ctrl+u")
            await pilot.press(*"Up Next")
            await pilot.press("enter")
            await pilot.pause()

            view = screen.column_views[0]
            self.assertEqual(view.column.slug, "up-next")
            self.assertEqual([card.card_task.slug for card in view.cards],
                             ["first", "second"])

    async def test_escape_leaves_the_name_alone(self) -> None:
        """A cancelled rename writes nothing and closes the field."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "r")
            await pilot.pause()
            await pilot.press(*"zzz")
            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(_headers(screen)[0].naming)
            self.assertEqual(_columns(self.svc), ["todo", "doing", "done"])


    async def test_focus_leaving_the_field_closes_it(self) -> None:
        """Clicking away is a way out of naming, and writes nothing."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "r")
            await pilot.pause()
            screen.column_views[1].focus()
            await pilot.pause()

            self.assertFalse(_headers(screen)[0].naming)
            self.assertIs(pilot.app.focused, screen.column_views[1])
            self.assertEqual(_columns(self.svc), ["todo", "doing", "done"])


class TestCreatingAColumn(unittest.IsolatedAsyncioTestCase):
    """`n` names a new column in a draft drawn to the right of this one."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_draft_is_drawn_to_the_right(self) -> None:
        """The draft takes the place the column will occupy."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "n")
            await pilot.pause()

            panels = list(screen.query(ColumnPanel))
            self.assertEqual(len(panels), 4)
            self.assertTrue(panels[1].draft)
            self.assertTrue(panels[1].header.naming)

    async def test_created_column_lands_where_the_draft_was(self) -> None:
        """Naming the draft creates the column in that position, not at the end."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("c", "n")
            await pilot.pause()
            await pilot.press(*"Review")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["todo", "review", "doing", "done"])

    async def test_focus_leaving_the_field_discards_the_draft(self) -> None:
        """A draft abandoned by clicking away goes, and the click keeps focus."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "n")
            await pilot.pause()
            screen.column_views[0].focus()
            await pilot.pause()

            self.assertEqual(len(list(screen.query(ColumnPanel))), 3)
            self.assertIs(pilot.app.focused, screen.column_views[0])

    async def test_created_from_the_last_column_lands_at_the_end(self) -> None:
        """A column named on the last header is created after it, not before."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("right", "right", "c", "n")
            await pilot.pause()
            await pilot.press(*"Archive")
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["todo", "doing", "done", "archive"])
            self.assertIs(pilot.app.focused, _headers(screen)[3])

    async def test_escape_discards_the_draft(self) -> None:
        """A draft that is never named leaves no column and no panel behind."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "n")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(len(list(screen.query(ColumnPanel))), 3)
            self.assertEqual(_columns(self.svc), ["todo", "doing", "done"])
            self.assertIs(pilot.app.focused, _headers(screen)[0])


class TestFocusLeftOnARemovedHeader(unittest.IsolatedAsyncioTestCase):
    """The board survives a header that was focused after it was taken off screen."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_a_detached_header_names_no_column(self) -> None:
        """
        Focus can outlive the header holding it, and the board must not follow it.

        Textual defers focus, so a header focused as the board is rebuilt can be
        pruned before the deferred call runs — the prune had no focus to reset,
        and the screen is left pointing at a header with no panel.  Reading the
        focused column then has to fall back rather than raise, which is what
        crashed the app when a column was created from its header.
        """
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            header = _headers(screen)[0]
            await header.panel.remove()
            await pilot.pause()

            screen.focused = header
            self.assertIsNone(header.parent)

            self.assertIs(screen.focused_column, screen.column_views[0])
            # And nothing on the way to a task raises either.
            self.assertIsNone(screen.selected_task)


class TestDeletingAColumn(unittest.IsolatedAsyncioTestCase):
    """`d` deletes the column, once the confirmation comes back."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_confirming_deletes_the_column(self) -> None:
        """The column and its cards go, and focus lands on the one that follows."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "d")
            await pilot.pause()
            self.assertIsInstance(pilot.app.screen, ConfirmScreen)

            await pilot.press("y")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["doing", "done"])
            self.assertIs(pilot.app.focused, _headers(screen)[0])

    async def test_the_prompt_names_the_column_the_way_the_board_does(self) -> None:
        """The name carries the header's colour; the path sits muted beneath it."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("c", "d")
            await pilot.pause()

            content = pilot.app.screen.query_one("#confirm-prompt", Static).render()
            styles = {
                content.plain[span.start : span.end]: span.style
                for span in content.spans
            }

            self.assertEqual(
                content.plain.splitlines(),
                ["Delete column todo and its 2 tasks?", "/alpha/todo"],
            )
            self.assertEqual(styles["todo"], "$primary")
            self.assertEqual(styles["/alpha/todo"], "$text-muted")

    async def test_cancelling_keeps_the_column(self) -> None:
        """Answering no writes nothing."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("c", "d")
            await pilot.pause()
            await pilot.press("n")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["todo", "doing", "done"])


class TestReorderingAColumn(unittest.IsolatedAsyncioTestCase):
    """Shift + ←/→ move the focused column along the board."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_shift_right_moves_the_column_along(self) -> None:
        """The column swaps with the one to its right, and focus follows it."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "shift+right")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["doing", "todo", "done"])
            self.assertIs(pilot.app.focused, _headers(screen)[1])

    async def test_the_panels_are_moved_rather_than_rebuilt(self) -> None:
        """
        A reorder redraws nothing: the same widgets are still on the board.

        Only where two columns sit has changed, so the panels are moved within
        their container — every card, scroll position, and the focused header
        survive the move because none of them is built again.
        """
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            before = {id(panel) for panel in screen.query(ColumnPanel)}
            cards = {id(card) for card in screen.column_views[0].cards}

            await pilot.press("c", "shift+right")
            await pilot.pause()

            panels = list(screen.query(ColumnPanel))
            self.assertEqual({id(panel) for panel in panels}, before)
            self.assertEqual(
                [panel.column.slug for panel in panels], ["doing", "todo", "done"]
            )
            # The moved column's cards are the very same widgets.
            self.assertEqual({id(card) for card in panels[1].view.cards}, cards)

    async def test_the_moved_columns_learn_their_new_positions(self) -> None:
        """The two panels that swapped are handed their new records."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "shift+right")
            await pilot.pause()

            panels = list(screen.query(ColumnPanel))
            self.assertEqual([panel.column.position for panel in panels], [0, 1, 2])
            self.assertEqual(panels[1].view.column.position, 1)
            self.assertEqual(panels[1].header.column.position, 1)

    async def test_shift_left_at_the_end_does_nothing(self) -> None:
        """The leftmost column has nowhere to go."""
        async with self.app.run_test() as pilot:
            await _board_screen(pilot)

            await pilot.press("c", "shift+left")
            await pilot.pause()

            self.assertEqual(_columns(self.svc), ["todo", "doing", "done"])


class TestHeaderReplacesTheCardActions(unittest.IsolatedAsyncioTestCase):
    """A focused header takes the keys the cards would otherwise answer to."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_n_does_not_open_the_task_form(self) -> None:
        """`n` on a header starts a column, not a task."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "n")
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, BoardScreen)
            self.assertTrue(any(panel.draft for panel in screen.query(ColumnPanel)))

    async def test_only_the_column_actions_are_left(self) -> None:
        """A focused header is a mode: the board's own keys are all refused."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c")
            await pilot.pause()

            for action in (
                "delete_task",
                "move_task",
                "nav_up",
                "switch_board",
                "command",
                "filter",
                "toggle_sidebar",
                "toggle_density",
                "reload_board",
            ):
                self.assertFalse(screen.check_action(action, ()), action)

            # What is left moves between the columns and back to the cards.
            self.assertTrue(screen.check_action("nav_right", ()))
            self.assertTrue(screen.check_action("step_focus", ()))

    async def test_board_keys_do_nothing_on_a_header(self) -> None:
        """`b` opens no board switcher while a header holds focus."""
        async with self.app.run_test() as pilot:
            screen = await _board_screen(pilot)

            await pilot.press("c", "b")
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, BoardScreen)
            self.assertIs(pilot.app.focused, _headers(screen)[0])


if __name__ == "__main__":
    unittest.main()
