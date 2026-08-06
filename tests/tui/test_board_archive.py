"""Tests for archiving from the board screen, and the archive column it hides."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.screens.confirm import ConfirmScreen
from kanban.tui.widgets import ColumnView


def _make_service() -> KanbanService:
    """Return a service holding one board with two tasks in its first column."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    svc.create_board("Alpha", columns=[("To Do", Slug("todo")), ("Done", Slug("done"))])
    svc.set_board(Slug("alpha"))

    for title in ("first", "second"):
        svc.create_task(Path("/alpha/todo"), TaskCreateParams(title=title))

    return svc


def _screen(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen under whatever is on top of it."""
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


def _columns(pilot: Pilot[None]) -> list[str]:
    """Return the slugs of the columns the board has drawn."""
    return [view.column.slug for view in _screen(pilot).query(ColumnView)]


def _shown(pilot: Pilot[None], column: str) -> list[str]:
    """Return the slugs `column` has cards mounted for."""
    views = _screen(pilot).query(ColumnView)
    view = next((v for v in views if v.column.slug == column), None)
    return [] if view is None else [card.card_task.slug for card in view.cards]


def _cards(pilot: Pilot[None], column: str) -> list[object]:
    """Return the card widgets `column` holds, as objects, so identity can be checked."""
    views = _screen(pilot).query(ColumnView)
    view = next((v for v in views if v.column.slug == column), None)
    return [] if view is None else list(view.cards)


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


class TestBoardArchiveColumn(unittest.IsolatedAsyncioTestCase):
    """`A` shows the archive column and hides it again."""

    async def test_archive_column_is_hidden_by_default(self) -> None:
        """The board opens on the workflow, without the archive."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()

            self.assertEqual(_columns(pilot), ["todo", "done"])

    async def test_shift_a_shows_the_archive_column(self) -> None:
        """`A` draws the archive alongside the workflow columns."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()

            self.assertEqual(_columns(pilot), ["todo", "done", "archive"])

    async def test_shift_a_hides_it_again(self) -> None:
        """`A` a second time puts the board back."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()

            self.assertEqual(_columns(pilot), ["todo", "done"])

    async def test_showing_the_archive_leaves_the_other_columns_standing(self) -> None:
        """The workflow columns are added to, not rebuilt: the same cards stay."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            before = _cards(pilot, "todo")

            await pilot.press("A")
            await pilot.pause()

            after = _cards(pilot, "todo")
            self.assertEqual(len(after), len(before))
            for old, new in zip(before, after):
                self.assertIs(old, new)

    async def test_hiding_the_archive_leaves_the_other_columns_standing(self) -> None:
        """Removing the column rebuilds nothing either."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            before = _cards(pilot, "todo")

            await pilot.press("A")
            await pilot.pause()

            for old, new in zip(before, _cards(pilot, "todo")):
                self.assertIs(old, new)

    async def test_the_selection_survives_the_toggle(self) -> None:
        """The card the user was on is still selected, and still focused."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("down")
            await pilot.pause()

            await pilot.press("A")
            await pilot.pause()

            screen = _screen(pilot)
            selected = screen.selected_task
            self.assertIsNotNone(selected)
            self.assertEqual(selected.slug, "second")

    async def test_hiding_hands_focus_back_when_it_was_in_the_archive(self) -> None:
        """Focus cannot stay on a column that has gone; it lands on the last one."""
        svc = _make_service()
        svc.archive_task(Path("/alpha/todo/first"))

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            await pilot.press("right", "right")
            await pilot.pause()
            self.assertEqual(_focused_column(pilot), "archive")

            await pilot.press("A")
            await pilot.pause()

            self.assertEqual(_focused_column(pilot), "done")

    async def test_archived_cards_are_shown_once_the_column_is(self) -> None:
        """Showing the archive shows what is in it."""
        svc = _make_service()
        svc.archive_task(Path("/alpha/todo/first"))

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            self.assertEqual(_shown(pilot, "todo"), ["second"])

            await pilot.press("A")
            await pilot.pause()

            self.assertEqual(_shown(pilot, "archive"), ["first"])


class TestBoardArchiveTask(unittest.IsolatedAsyncioTestCase):
    """`a` archives the focused card, and brings an archived one back."""

    async def test_a_asks_before_archiving(self) -> None:
        """A confirmation stands between the key and the move."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()

            self.assertIsInstance(pilot.app.screen, ConfirmScreen)

    async def test_cancelling_leaves_the_task_alone(self) -> None:
        """Answering no writes nothing."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(svc.get_task(Path("/alpha/todo/first")).column, "todo")

    async def test_confirming_archives_the_task(self) -> None:
        """The task moves into the archive column."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(
                [t.slug for t in svc.get_tasks(Path("/alpha/archive"))], ["first"]
            )

    async def test_the_archived_card_leaves_the_column(self) -> None:
        """With the archive hidden, the card simply goes."""
        svc = _make_service()
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(_shown(pilot, "todo"), ["second"])

    async def test_a_brings_an_archived_task_back(self) -> None:
        """On an archived card, `a` returns it to the first column."""
        svc = _make_service()
        svc.archive_task(Path("/alpha/todo/first"))

        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await pilot.press("A")
            await pilot.pause()
            # The archive is the rightmost column, and holds the one card.
            await pilot.press("right", "right")
            await pilot.pause()
            await pilot.press("a")
            await _confirm(pilot)

            self.assertEqual(svc.get_task(Path("/alpha/todo/first")).column, "todo")
            self.assertEqual(svc.get_tasks(Path("/alpha/archive")), [])


if __name__ == "__main__":
    unittest.main()
