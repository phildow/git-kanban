"""Tests for moving the board's selection from the task detail screen."""

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
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.board import BoardScreen
from kanban.tui.screens.task_detail import TaskDetailScreen


def _make_service() -> KanbanService:
    """Return a service holding one board with three columns, one of them empty."""
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
    svc.create_task("/alpha/doing", TaskCreateParams(title="third"))

    return svc


async def _open_detail(pilot: Pilot[None]) -> TaskDetailScreen:
    """Open the detail modal on the selected card, and return it."""
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, TaskDetailScreen))


def _board(pilot: Pilot[None]) -> BoardScreen:
    """Return the board screen under the modal."""
    return next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))


class TestDetailNavigation(unittest.IsolatedAsyncioTestCase):
    """The arrows and `h/j/k/l` keep moving the selection while the detail screen is open."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_down_shows_the_next_card_in_the_column(self) -> None:
        """`j` moves to the next card and the screen draws it."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)
            self.assertEqual(detail.detail_task.slug, "first")

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(detail.detail_task.slug, "second")

    async def test_right_shows_the_next_column(self) -> None:
        """`l` moves to the card selected in the column to the right."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            await pilot.press("l")
            await pilot.pause()

            self.assertEqual(detail.detail_task.slug, "third")

    async def test_arrow_keys_navigate_too(self) -> None:
        """The arrows move the selection the same way the letters do."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(detail.detail_task.slug, "second")

            await pilot.press("up")
            await pilot.pause()
            self.assertEqual(detail.detail_task.slug, "first")

    async def test_heading_and_metadata_follow_the_selection(self) -> None:
        """The title, path, and metadata block are redrawn for the new task."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            await pilot.press("j")
            await pilot.pause()

            title = detail.query_one(".-task-title", Static)
            path = detail.query_one(".-task-path", Static)

            self.assertIn("second", str(title.content))
            self.assertIn("/alpha/todo/second", str(path.content))

    async def test_empty_column_is_not_navigated_into(self) -> None:
        """A column with no card to show leaves the screen on the task it has."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            # todo → doing → done, the last of which holds nothing.
            await pilot.press("l", "l")
            await pilot.pause()

            self.assertEqual(detail.detail_task.slug, "third")

    async def test_end_of_the_column_holds_still(self) -> None:
        """Moving past the last card leaves the selection where it is."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            await pilot.press("j", "j", "j")
            await pilot.pause()

            self.assertEqual(detail.detail_task.slug, "second")

    async def test_board_selection_survives_the_close(self) -> None:
        """Closing the screen leaves the board on the card navigated to."""
        async with self.app.run_test() as pilot:
            await _open_detail(pilot)
            board = _board(pilot)

            await pilot.press("l")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            selected = board.selected_task
            self.assertIsNotNone(selected)
            assert selected is not None
            self.assertEqual(selected.slug, "third")
            self.assertEqual(selected.column, "doing")

    async def test_the_board_focuses_the_column_being_read(self) -> None:
        """
        The board's own focus follows the selection, so one column reads as focused.

        Focus is per screen: the board keeps its own while the modal holds the
        app's, and a column left focused behind the modal would go on being
        drawn as the focused one alongside the column actually being read.
        """
        async with self.app.run_test() as pilot:
            await _open_detail(pilot)
            board = _board(pilot)
            panels = board.column_panels

            self.assertIs(board.focused, panels[0].view)

            await pilot.press("l")
            await pilot.pause()

            self.assertIs(board.focused, panels[1].view)

    async def test_shifted_keys_scroll_the_body(self) -> None:
        """`shift+down` and `K` scroll the body without moving the selection."""
        from kanban.tui.screens.task_detail import DetailBody

        self.svc.update_task(
            "/alpha/todo/first", TaskUpdateParams(description="\n\n".join("line" for _ in range(200)))
        )

        async with self.app.run_test(size=(80, 24)) as pilot:
            detail = await _open_detail(pilot)
            body = detail.query_one(DetailBody)
            self.assertEqual(body.scroll_offset.y, 0)

            await pilot.press("shift+down", "shift+down")
            await pilot.pause()

            self.assertGreater(body.scroll_offset.y, 0)
            self.assertEqual(detail.detail_task.slug, "first")

            scrolled = body.scroll_offset.y
            await pilot.press("K")
            await pilot.pause()

            self.assertLess(body.scroll_offset.y, scrolled)
            self.assertEqual(detail.detail_task.slug, "first")

    async def test_scrolling_resets_when_the_selection_moves(self) -> None:
        """A task navigated to is read from its start."""
        from kanban.tui.screens.task_detail import DetailBody

        self.svc.update_task(
            "/alpha/todo/first", TaskUpdateParams(description="\n\n".join("line" for _ in range(200)))
        )

        async with self.app.run_test(size=(80, 24)) as pilot:
            detail = await _open_detail(pilot)
            body = detail.query_one(DetailBody)

            await pilot.press("shift+down", "shift+down")
            await pilot.pause()
            self.assertGreater(body.scroll_offset.y, 0)

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(detail.detail_task.slug, "second")
            self.assertEqual(body.scroll_offset.y, 0)

    async def test_edit_opens_on_the_task_shown(self) -> None:
        """`e` edits the task navigated to, not the one the screen opened with."""
        from kanban.tui.screens.task_form import TaskFormScreen

        async with self.app.run_test() as pilot:
            await _open_detail(pilot)

            await pilot.press("j")
            await pilot.pause()
            await pilot.press("e")
            await pilot.pause()

            form = next(
                s for s in pilot.app.screen_stack if isinstance(s, TaskFormScreen)
            )
            self.assertIsNotNone(form.form_task)
            assert form.form_task is not None
            self.assertEqual(form.form_task.slug, "second")
