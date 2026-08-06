"""Tests for redrawing only the cards an operation changed, not the whole column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Priority, Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.widgets import CardWidget, ColumnView, CommandBar


def _make_service() -> KanbanService:
    """Return a service holding one board of three columns, the first with three tasks."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Done", "done"), ("Later", "later")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    for title in ("first", "second", "third"):
        svc.create_task(Path("/alpha/todo"), TaskCreateParams(title=title))
    svc.create_task(Path("/alpha/done"), TaskCreateParams(title="done task"))
    svc.create_task(Path("/alpha/later"), TaskCreateParams(title="later task"))

    return svc


def _view(pilot: Pilot[None], column: str) -> ColumnView:
    """Return the mounted view of the named column."""
    return next(
        view
        for view in pilot.app.screen.query(ColumnView)
        if view.column.slug == Slug(column)
    )


def _cards(pilot: Pilot[None], column: str) -> list[CardWidget]:
    """Return the card widgets currently drawn in the named column, in display order."""
    return _view(pilot, column).cards


def _slugs(pilot: Pilot[None], column: str) -> list[str]:
    """Return the slugs of the tasks the named column is drawing, in display order."""
    return [card.card_task.slug for card in _cards(pilot, column)]


def _card_for(pilot: Pilot[None], column: str, slug: str) -> CardWidget:
    """Return the card drawing the named task."""
    return next(
        card for card in _cards(pilot, column) if card.card_task.slug == Slug(slug)
    )


async def _run(pilot: Pilot[None], line: str) -> None:
    """Open the command bar if needed, type `line`, and submit it."""
    bar = pilot.app.screen.query_one(CommandBar)
    if not bar.has_class("-visible"):
        await pilot.press("slash")
        await pilot.pause()

    bar.value = line
    await pilot.press("enter")
    await pilot.pause()
    await pilot.pause()


async def _filter(pilot: Pilot[None], query: str) -> None:
    """Open the filter bar, type `query`, and submit it."""
    await pilot.press("colon")
    await pilot.pause()
    await pilot.press(*query)
    await pilot.press("enter")
    await pilot.pause()


class TestEdit(unittest.IsolatedAsyncioTestCase):
    """An edit repaints one card and leaves every card in the column standing."""

    async def test_the_cards_are_the_same_widgets(self) -> None:
        """The edited card included: it is handed the new record, not rebuilt."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            before = _cards(pilot, "todo")

            await _run(pilot, "update first --priority high")

            self.assertEqual(before, _cards(pilot, "todo"))

    async def test_the_edited_card_shows_the_new_value(self) -> None:
        """Keeping the widget does not mean keeping the stale task."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "update first --priority high")

            self.assertEqual(_card_for(pilot, "todo", "first").card_task.priority, Priority.HIGH)

    async def test_the_cards_beside_it_keep_their_task(self) -> None:
        """A card the edit did not name is not handed anything."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            second = _card_for(pilot, "todo", "second").card_task

            await _run(pilot, "update first --priority high")

            self.assertEqual(_card_for(pilot, "todo", "second").card_task, second)


class TestCreate(unittest.IsolatedAsyncioTestCase):
    """A new card is mounted beside the cards already drawn."""

    async def test_the_existing_cards_survive(self) -> None:
        """Creating a task rebuilds none of the cards already in the column."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            before = _cards(pilot, "todo")

            await _run(pilot, "create todo fourth")

            self.assertEqual(before, _cards(pilot, "todo")[:3])

    async def test_the_new_card_is_drawn(self) -> None:
        """The card that was built is the one the command created."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await _run(pilot, "create todo fourth")

            self.assertEqual(_slugs(pilot, "todo"), ["first", "second", "third", "fourth"])


class TestDelete(unittest.IsolatedAsyncioTestCase):
    """A deleted card is removed and the cards around it are left alone."""

    async def test_the_remaining_cards_survive(self) -> None:
        """The gap closes without the column being rebuilt around it."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            first, second, third = _cards(pilot, "todo")

            await _run(pilot, "delete second --force")

            self.assertEqual([first, third], _cards(pilot, "todo"))


class TestReorderWithinColumn(unittest.IsolatedAsyncioTestCase):
    """Reordering moves the cards that change place and rebuilds none of them."""

    async def test_the_cards_are_the_same_widgets_in_a_new_order(self) -> None:
        """A staged move committed within a column moves widgets, it does not remake them."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            first, second, third = _cards(pilot, "todo")

            await pilot.press("m")
            await pilot.press("down")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(_slugs(pilot, "todo"), ["second", "first", "third"])
            self.assertEqual([second, first, third], _cards(pilot, "todo"))

    async def test_a_staged_position_rebuilds_no_card(self) -> None:
        """The preview drawn on each keystroke moves the cards it previews."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            before = set(_cards(pilot, "todo"))

            await pilot.press("m")
            await pilot.press("down")
            await pilot.pause()

            self.assertEqual(before, set(_cards(pilot, "todo")))


class TestMoveBetweenColumns(unittest.IsolatedAsyncioTestCase):
    """A card crossing columns leaves the cards at both ends standing."""

    async def test_the_cards_it_left_behind_survive(self) -> None:
        """Only the card that went is taken off the source column."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            _, second, third = _cards(pilot, "todo")

            await _run(pilot, "move first done")

            self.assertEqual([second, third], _cards(pilot, "todo"))

    async def test_the_cards_it_joined_survive(self) -> None:
        """The destination gains a card without rebuilding the ones it had."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            done = _cards(pilot, "done")

            await _run(pilot, "move first done")

            self.assertEqual(done, _cards(pilot, "done")[:1])
            self.assertEqual(_slugs(pilot, "done"), ["done-task", "first"])


class TestFilter(unittest.IsolatedAsyncioTestCase):
    """Filtering takes cards off the board without rebuilding the ones that stay."""

    async def test_the_surviving_card_is_the_same_widget(self) -> None:
        """A card that goes on matching the filter is not redrawn for it."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            first = _card_for(pilot, "todo", "first")

            await _filter(pilot, "first")

            self.assertEqual(_slugs(pilot, "todo"), ["first"])
            self.assertEqual([first], _cards(pilot, "todo"))

    async def test_the_highlight_follows_the_task_that_held_it(self) -> None:
        """
        A card that changes index keeps the highlight, rather than the index keeping it.

        The filter is the case with no caller to name a selection afterwards, so
        the column has to carry the highlight across on its own.
        """
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")  # highlight "second", at index 1
            await pilot.pause()

            # "d" drops "first" and keeps the other two, so "second" ends up
            # first in the column it was second in.
            await _filter(pilot, "d")

            self.assertEqual(_slugs(pilot, "todo"), ["second", "third"])
            selected = _view(pilot, "todo").selected_task
            self.assertEqual(None if selected is None else selected.slug, Slug("second"))


class TestStagedCardStaysInView(unittest.IsolatedAsyncioTestCase):
    """A card staged past the edge of a scrolling column is scrolled to."""

    @staticmethod
    def _make_tall_service() -> KanbanService:
        """Return a service whose first column holds more cards than fit on screen."""
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        repo = InMemoryRepository(root=temp_dir)
        svc = KanbanService(
            repository=repo,
            index_service=MagicMock(),
            change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
        )

        repo.create_board("alpha", slug=Slug("alpha"))
        repo.create_column(Slug("alpha"), "To Do", slug=Slug("todo"))
        svc.set_board(Slug("alpha"))

        for index in range(20):
            svc.create_task(Path("/alpha/todo"), TaskCreateParams(title=f"task {index:02d}"))

        return svc

    @staticmethod
    def _moving_in_view(pilot: Pilot[None]) -> bool:
        """Return whether the card being staged is inside the column's visible area."""
        view = _view(pilot, "todo")
        moving = next(card for card in view.cards if card.has_class("-moving"))
        return view.content_region.contains_region(moving.region)

    async def test_stepping_down_keeps_the_card_in_view(self) -> None:
        """
        Each press follows the card past the bottom edge.

        A card that has just been moved still carries the region it had before
        the move, so a scroll taken during the redraw lands on where the card
        was — leaving it a row outside the visible area.
        """
        async with KanbanApp(self._make_tall_service()).run_test(size=(120, 24)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()

            for step in range(10):
                await pilot.press("down")
                await pilot.pause()
                self.assertTrue(self._moving_in_view(pilot), f"out of view after {step + 1} steps")

    async def test_staging_to_the_bottom_scrolls_all_the_way(self) -> None:
        """Alt+down jumps the card to the end, and the column follows it there."""
        async with KanbanApp(self._make_tall_service()).run_test(size=(120, 24)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()

            await pilot.press("alt+down")
            await pilot.pause()

            view = _view(pilot, "todo")
            self.assertEqual(view.index, 19)
            self.assertEqual(view.scroll_y, view.max_scroll_y)
            self.assertTrue(self._moving_in_view(pilot))

    async def test_staging_back_to_the_top_scrolls_back(self) -> None:
        """And alt+up brings the column back with it."""
        async with KanbanApp(self._make_tall_service()).run_test(size=(120, 24)) as pilot:
            await pilot.pause()
            await pilot.press("m")
            await pilot.pause()
            await pilot.press("alt+down")
            await pilot.pause()

            await pilot.press("alt+up")
            await pilot.pause()

            view = _view(pilot, "todo")
            self.assertEqual(view.index, 0)
            self.assertEqual(view.scroll_y, 0)
            self.assertTrue(self._moving_in_view(pilot))


class TestRename(unittest.IsolatedAsyncioTestCase):
    """A renamed task keeps its card: the slug changed, the task did not."""

    async def test_the_card_survives_a_rename(self) -> None:
        """Cards are matched on id, which a rename leaves alone."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            before = _cards(pilot, "todo")

            await _run(pilot, "rename first Renamed")

            self.assertEqual(_slugs(pilot, "todo"), ["renamed", "second", "third"])
            self.assertEqual(before, _cards(pilot, "todo"))


if __name__ == "__main__":
    unittest.main()
