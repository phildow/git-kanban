"""Tests for how the task detail screen draws a task with nothing written in it."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from textual.pilot import Pilot
from textual.widgets import Static
from textual.widgets._markdown import MarkdownH1, MarkdownH2

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.screens.task_detail import TaskDetailScreen, _is_body_empty


def _make_service() -> KanbanService:
    """Return a service holding one column with an empty task above a described one."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    svc.set_board(Slug("alpha"))

    svc.create_task("/alpha/todo", TaskCreateParams(title="bare"))
    svc.create_task(
        "/alpha/todo", TaskCreateParams(title="written", description="something")
    )

    return svc


def _make_commented_service() -> KanbanService:
    """Return a service holding one described task carrying a comment."""
    temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    temp_dir.mkdir()
    repo = InMemoryRepository(root=temp_dir)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("alpha", slug="alpha")
    repo.create_column("alpha", "todo", slug="todo")
    svc.set_board(Slug("alpha"))

    svc.create_task(
        "/alpha/todo", TaskCreateParams(title="written", description="something")
    )
    svc.comment_task("/alpha/todo/written", "looking into it")

    return svc


async def _open_detail(pilot: Pilot[None]) -> TaskDetailScreen:
    """Open the detail modal on the selected card, and return it."""
    await pilot.pause()
    await pilot.press("enter")
    await pilot.pause()
    return next(s for s in pilot.app.screen_stack if isinstance(s, TaskDetailScreen))


class TestIsBodyEmpty(unittest.TestCase):
    """What counts as a body that says nothing about the task."""

    def test_no_text_at_all_is_empty(self) -> None:
        """A body with no text is empty."""
        self.assertTrue(_is_body_empty(""))

    def test_whitespace_is_empty(self) -> None:
        """A body of whitespace alone is empty."""
        self.assertTrue(_is_body_empty("\n\n  \n"))

    def test_description_heading_alone_is_empty(self) -> None:
        """The heading a task is created with, and nothing under it, is empty."""
        self.assertTrue(_is_body_empty("# Description\n"))

    def test_text_under_the_heading_is_not_empty(self) -> None:
        """A description written under the heading is not empty."""
        self.assertFalse(_is_body_empty("# Description\n\nsomething\n"))

    def test_comments_alone_are_not_empty(self) -> None:
        """A task with comments but no description still has a body to read."""
        self.assertFalse(_is_body_empty("# Description\n\n# Comments\n\n## 2026-08-01\n\nhi"))


class TestDetailEmptyBody(unittest.IsolatedAsyncioTestCase):
    """The placeholder stands in for a body with nothing in it."""

    async def asyncSetUp(self) -> None:
        self.svc = _make_service()
        self.app = KanbanApp(self.svc)

    async def test_placeholder_shown_for_an_empty_body(self) -> None:
        """A task with only its Description heading shows the dash."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            self.assertEqual(detail.detail_task.slug, "bare")
            placeholder = detail.query_one("#task-detail-empty", Static)
            self.assertTrue(placeholder.display)

    async def test_placeholder_hidden_once_a_written_task_is_shown(self) -> None:
        """Navigating to a task with a description hides the dash."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(detail.detail_task.slug, "written")
            placeholder = detail.query_one("#task-detail-empty", Static)
            self.assertFalse(placeholder.display)


class TestDetailHeadingSpacing(unittest.IsolatedAsyncioTestCase):
    """A heading in the body sits one row below what comes before it."""

    async def asyncSetUp(self) -> None:
        self.app = KanbanApp(_make_commented_service())

    async def test_description_heading_takes_no_row_above(self) -> None:
        """The `# Description` heading sits on the row the metadata already left."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            heading = detail.query_one(MarkdownH1)
            self.assertEqual(heading.styles.margin.top, 0)

    async def test_comment_headings_take_one_row_above(self) -> None:
        """The `# Comments` and dated `##` headings, below the first, take one row."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            headings = [*detail.query(MarkdownH1), *detail.query(MarkdownH2)][1:]
            self.assertGreater(len(headings), 0)
            for heading in headings:
                self.assertEqual(heading.styles.margin.top, 1)

    async def test_the_row_below_a_heading_is_kept(self) -> None:
        """Tightening the top leaves the row that separates a heading from its text."""
        async with self.app.run_test() as pilot:
            detail = await _open_detail(pilot)

            heading = detail.query_one(MarkdownH1)
            self.assertEqual(heading.styles.margin.bottom, 1)
