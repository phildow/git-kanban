"""Tests for where the highlight lands when a card leaves its column."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.widgets import CommandBar


def _make_service() -> KanbanService:
    """Return a service holding one board with three tasks in its first column."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    svc.create_board("Alpha", columns=[("To Do", Slug("todo")), ("Done", Slug("done"))])
    svc.set_board(Slug("alpha"))

    for title in ("first", "second", "third"):
        svc.create_task(Path("/alpha/todo"), TaskCreateParams(title=title))

    return svc


def _screen(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen under whatever is on top of it."""
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


def _selected(pilot: Pilot[None]) -> str | None:
    """Return the slug of the highlighted task, or None when there is none."""
    task = _screen(pilot).selected_task
    return None if task is None else task.slug


def _focused_column(pilot: Pilot[None]) -> str | None:
    """Return the slug of the column holding focus."""
    column = _screen(pilot).focused_column
    return None if column is None else column.column.slug


async def _confirm(pilot: Pilot[None]) -> None:
    """Answer the confirmation modal, and let the refresh that follows land."""
    await pilot.pause()
    await pilot.press("y")
    await pilot.pause()
    await pilot.pause()


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


class TestSelectionAfterDelete(unittest.IsolatedAsyncioTestCase):
    """`d` leaves the highlight on the card that closes the gap."""

    async def test_the_card_below_takes_the_highlight(self) -> None:
        """Deleting the middle card lands on the one that was under it."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await pilot.press("d")
            await _confirm(pilot)

            self.assertEqual(_selected(pilot), "third")

    async def test_the_first_card_lands_on_the_second(self) -> None:
        """Deleting the top card is no different: the next one comes up."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()

            await pilot.press("d")
            await _confirm(pilot)

            self.assertEqual(_selected(pilot), "second")

    async def test_the_last_card_falls_back_to_the_one_above(self) -> None:
        """With nothing below it, the highlight moves up rather than to the top."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down")
            await pilot.pause()

            await pilot.press("d")
            await _confirm(pilot)

            self.assertEqual(_selected(pilot), "second")

    async def test_the_only_card_leaves_nothing_selected(self) -> None:
        """An emptied column has no card to hand the highlight to."""
        svc = _make_service()
        svc.delete_task(Path("/alpha/todo/second"))
        svc.delete_task(Path("/alpha/todo/third"))

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            await pilot.press("d")
            await _confirm(pilot)

            self.assertIsNone(_selected(pilot))

    async def test_the_focus_stays_on_the_column(self) -> None:
        """The highlight moving within the column does not move the focus off it."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await pilot.press("d")
            await _confirm(pilot)

            self.assertEqual(_focused_column(pilot), "todo")


class TestSelectionAfterArchive(unittest.IsolatedAsyncioTestCase):
    """`a` leaves the highlight behind when the card goes somewhere unseen."""

    async def test_the_card_below_takes_the_highlight(self) -> None:
        """With the archive hidden the card is gone, so the next one takes over."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(_selected(pilot), "third")

    async def test_the_last_card_falls_back_to_the_one_above(self) -> None:
        """Archiving the bottom card moves the highlight up."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down", "down")
            await pilot.pause()

            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(_selected(pilot), "second")

    async def test_the_focus_does_not_follow_the_card_into_the_archive(self) -> None:
        """With the archive on screen the user still stays on the column they were on."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(_focused_column(pilot), "todo")
            self.assertEqual(_selected(pilot), "third")

    async def test_unarchiving_stays_in_the_archive(self) -> None:
        """Bringing a card back leaves the user in the archive, on the next card."""
        svc = _make_service()
        svc.archive_task(Path("/alpha/todo/first"))
        svc.archive_task(Path("/alpha/todo/second"))

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            # The archive is the rightmost column, and holds the two cards.
            await pilot.press("right", "right")
            await pilot.pause()

            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(_focused_column(pilot), "archive")
            self.assertEqual(_selected(pilot), "second")

    async def test_emptying_the_archive_leaves_the_focus_where_it_is(self) -> None:
        """The last card out of the archive leaves nothing to highlight, and no move."""
        svc = _make_service()
        svc.archive_task(Path("/alpha/todo/first"))

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            await pilot.press("right", "right")
            await pilot.pause()

            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(_focused_column(pilot), "archive")
            self.assertIsNone(_selected(pilot))


class TestSelectionAfterCommand(unittest.IsolatedAsyncioTestCase):
    """A command run from the bar leaves the highlight in the same place."""

    async def test_deleting_the_selected_card_lands_on_the_next(self) -> None:
        """The bar deletes the card the user was on; the one below takes over."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await _run(pilot, "delete second --force")

            self.assertEqual(_selected(pilot), "third")

    async def test_archiving_the_selected_card_lands_on_the_next(self) -> None:
        """A card sent to the hidden archive is gone from the board just the same."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await _run(pilot, "move second archive")

            self.assertEqual(_selected(pilot), "third")

    async def test_deleting_another_card_leaves_the_highlight_alone(self) -> None:
        """A command that did not touch the selected card does not move it."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await _run(pilot, "delete third --force")

            self.assertEqual(_selected(pilot), "second")


if __name__ == "__main__":
    unittest.main()
