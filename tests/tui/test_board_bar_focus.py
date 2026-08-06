"""Tests for the board keeping its column focus across the input bars."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.widgets import ColumnView


def _make_service() -> KanbanService:
    """Return a service holding one board of three columns, each with a task."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
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


def _focused_slug(pilot: Pilot[None]) -> Slug | None:
    """Return the slug of the column view holding focus, or None when none does."""
    focused = pilot.app.focused
    return focused.column.slug if isinstance(focused, ColumnView) else None


class TestBarFocusReturn(unittest.IsolatedAsyncioTestCase):
    """Closing a bar hands focus back to the column it was opened from."""

    async def test_filter_bar_returns_to_the_focused_column(self) -> None:
        """Escaping the filter bar lands on the column the user was on."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("right", "right")
            self.assertEqual(_focused_slug(pilot), Slug("done"))

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(_focused_slug(pilot), Slug("done"))

    async def test_command_bar_returns_to_the_focused_column(self) -> None:
        """Escaping the command bar lands on the column the user was on."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("right")

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(_focused_slug(pilot), Slug("doing"))

    async def test_a_submitted_filter_returns_to_the_focused_column(self) -> None:
        """Enter in the filter bar closes it on the column it was opened from."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("right")

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_focused_slug(pilot), Slug("doing"))

    async def test_a_submitted_command_returns_to_the_focused_column(self) -> None:
        """An empty command line closes the bar on the column it was opened from."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("right", "right")

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_focused_slug(pilot), Slug("done"))

    async def test_a_typed_filter_returns_to_the_focused_column(self) -> None:
        """A filter that hides the selected card still closes on its column."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("right", "right")

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press(*"todo")
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            self.assertEqual(_focused_slug(pilot), Slug("done"))

    async def test_clearing_the_filter_leaves_the_focus_alone(self) -> None:
        """Escape with the bar closed clears the filter without moving focus."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("right", "right")

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press(*"todo")
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("escape")  # the filter is still on; this clears it
            await pilot.pause()

            self.assertTrue(_board(pilot)._filter.is_empty)
            self.assertEqual(_focused_slug(pilot), Slug("done"))
