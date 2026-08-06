"""Tests for the filter bar standing open while the filter it holds is in force."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.widgets import ColumnView, CommandBar, FilterBar


def _make_service() -> KanbanService:
    """Return a service holding one board of three columns, each with a task."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Doing", "doing"), ("Done", "done")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    for slug in ("todo", "doing", "done"):
        svc.create_task(f"/alpha/{slug}", TaskCreateParams(title=f"{slug} task"))

    return svc


def _board(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen under the app."""
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


def _filter_bar(pilot: Pilot[None]) -> FilterBar:
    """Return the board's filter bar."""
    return _board(pilot).query_one(FilterBar)


async def _apply_filter(pilot: Pilot[None], query: str) -> None:
    """Open the filter bar, type `query`, and submit it."""
    await pilot.press("colon")
    await pilot.pause()
    await pilot.press(*query)
    await pilot.press("enter")
    await pilot.pause()


class TestSubmittedFilterStands(unittest.IsolatedAsyncioTestCase):
    """Enter keeps the filter and the bar showing it, and returns to the board."""

    async def test_the_bar_stays_visible(self) -> None:
        """The query that is filtering the board stays on screen."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            bar = _filter_bar(pilot)
            self.assertTrue(bar.has_class("-visible"))
            self.assertEqual(bar.value, "todo")

    async def test_the_bar_is_marked_active(self) -> None:
        """The bar takes the styling that says the filter is in force."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            self.assertTrue(_filter_bar(pilot).has_class("-active"))

    async def test_the_focus_returns_to_the_board(self) -> None:
        """The cards take the focus back, so the board's keys work again."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            self.assertIsInstance(pilot.app.focused, ColumnView)

    async def test_the_filter_still_narrows_the_board(self) -> None:
        """The cards the query excludes stay off the board."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            board = _board(pilot)
            counts = {view.column.slug: len(view.children) for view in board.column_views}
            self.assertEqual(counts[Slug("todo")], 1)
            self.assertEqual(counts[Slug("done")], 0)

    async def test_an_empty_filter_takes_the_bar_down(self) -> None:
        """Nothing typed leaves nothing to show, so the bar closes."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("colon")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            bar = _filter_bar(pilot)
            self.assertFalse(bar.has_class("-visible"))
            self.assertFalse(bar.has_class("-active"))

    async def test_an_unparsed_query_keeps_the_focus(self) -> None:
        """A half-typed flag is not applied: the bar stays open to be finished."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "-p")

            bar = _filter_bar(pilot)
            self.assertTrue(bar.has_class("-unparsed"))
            self.assertFalse(bar.has_class("-active"))
            self.assertIs(pilot.app.focused, bar)


class TestEscapeClearsTheStandingFilter(unittest.IsolatedAsyncioTestCase):
    """Escape on the board clears the filter and takes the bar down."""

    async def test_the_bar_is_hidden(self) -> None:
        """One escape from the board closes the bar it left standing."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            await pilot.press("escape")
            await pilot.pause()

            bar = _filter_bar(pilot)
            self.assertFalse(bar.has_class("-visible"))
            self.assertFalse(bar.has_class("-active"))
            self.assertEqual(bar.value, "")

    async def test_the_cards_come_back(self) -> None:
        """Clearing the filter restores the cards it was hiding."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            await pilot.press("escape")
            await pilot.pause()

            board = _board(pilot)
            counts = {view.column.slug: len(view.children) for view in board.column_views}
            self.assertEqual(counts[Slug("done")], 1)

    async def test_the_focus_stays_where_it_is(self) -> None:
        """Escape is pressed on the board, and leaves the card the user is on."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "task")
            await pilot.press("right", "right")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            focused = pilot.app.focused
            assert isinstance(focused, ColumnView)
            self.assertEqual(focused.column.slug, Slug("done"))


class TestReopeningTheFilterBar(unittest.IsolatedAsyncioTestCase):
    """The standing query is what the bar reopens on."""

    async def test_the_query_is_kept(self) -> None:
        """Reopening the bar shows the filter that is running, ready to edit."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            await pilot.press("colon")
            await pilot.pause()

            bar = _filter_bar(pilot)
            self.assertEqual(bar.value, "todo")
            self.assertIs(pilot.app.focused, bar)

    async def test_the_active_styling_is_dropped(self) -> None:
        """A bar being typed into reads as one being typed into."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            await pilot.press("colon")
            await pilot.pause()

            self.assertFalse(_filter_bar(pilot).has_class("-active"))


class TestTheCommandBarTakesTheStrip(unittest.IsolatedAsyncioTestCase):
    """Both bars sit in the same row, so a standing filter yields to a command."""

    async def test_opening_the_command_bar_hides_the_filter_bar(self) -> None:
        """The command bar takes the strip while it is open."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            await pilot.press("slash")
            await pilot.pause()

            bar = _filter_bar(pilot)
            self.assertFalse(bar.has_class("-visible"))
            self.assertTrue(bar.has_class("-active"))

    async def test_closing_the_command_bar_brings_the_filter_back(self) -> None:
        """The filter never stopped running, and shows again with the strip free."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _apply_filter(pilot, "todo")

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            bar = _filter_bar(pilot)
            self.assertTrue(bar.has_class("-visible"))
            self.assertTrue(bar.has_class("-active"))
            self.assertFalse(_board(pilot).query_one(CommandBar).has_class("-visible"))
