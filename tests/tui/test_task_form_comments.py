"""Tests for how the task form presents the comments already on a task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Markdown

from kanban.models import Slug
from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.task_detail import TaskDetailScreen
from kanban.tui.screens.task_form import TaskFormScreen

COMMENT = "Investigating. The token expires early."


def _make_service(*, comment: str | None = COMMENT) -> KanbanService:
    """Return a service holding one task, commented on unless `comment` is None."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(InMemoryChangeTracker(), repo),
    )

    repo.create_board("Alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "To Do", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))
    svc.create_task("/alpha/todo", TaskCreateParams(title="Fix login bug"))

    if comment is not None:
        svc.comment_task("/alpha/todo/fix-login-bug", comment)

    return svc


async def _open_form(pilot: Pilot[None]) -> TaskFormScreen:
    """Open the edit form on the only task, and return it."""
    await pilot.pause()
    await pilot.press("e")
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, TaskFormScreen))


async def _open_detail(pilot: Pilot[None]) -> TaskDetailScreen:
    """Open the detail modal on the only task, and return it."""
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, TaskDetailScreen))


class TestTaskFormComments(unittest.IsolatedAsyncioTestCase):
    """The comments already on a task are shown as rendered markdown."""

    async def test_comments_are_rendered_as_markdown(self) -> None:
        """The form shows the existing comments through a Markdown widget."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            form = await _open_form(pilot)
            comments = form.query_one("#field-comments", Markdown)

            self.assertIn(COMMENT, comments.source)

    async def test_dated_heading_is_shown(self) -> None:
        """Each comment's own `##` heading is part of what the form renders."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            form = await _open_form(pilot)
            comments = form.query_one("#field-comments", Markdown)

            self.assertIn("## ", comments.source)

    async def test_no_comments_block_without_comments(self) -> None:
        """A task with no comments has no comments block at all."""
        async with KanbanApp(_make_service(comment=None)).run_test() as pilot:
            form = await _open_form(pilot)

            self.assertEqual(len(form.query("#field-comments")), 0)


class TestTaskFormCommentsMatchTheDetailScreen(unittest.IsolatedAsyncioTestCase):
    """Comments look the same in the form as they do in the detail modal."""

    async def test_background_matches_the_detail_screen(self) -> None:
        """
        The comments sit on the dialog's own background in both screens.

        A fill of their own would make them read as a field to type into, which
        is the one thing they are not — comments are append-only.
        """
        async with KanbanApp(_make_service()).run_test() as pilot:
            detail = await _open_detail(pilot)
            expected = detail.query_one(Markdown).background_colors[1]

            await pilot.press("escape")
            form = await _open_form(pilot)
            actual = form.query_one("#field-comments", Markdown).background_colors[1]

            self.assertEqual(actual, expected)

    async def test_comments_read_the_same_in_both(self) -> None:
        """The text the form renders is the text the detail modal renders."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            detail = await _open_detail(pilot)
            body = detail.query_one(Markdown).source

            await pilot.press("escape")
            form = await _open_form(pilot)
            comments = form.query_one("#field-comments", Markdown).source

            self.assertIn(comments, body)


if __name__ == "__main__":
    unittest.main()
