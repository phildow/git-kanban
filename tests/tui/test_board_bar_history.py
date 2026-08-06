"""Tests for the board's input bars cycling and keeping their history."""

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
from kanban.tui.widgets import CommandBar, FilterBar


class _LocalRepository(InMemoryRepository):
    """
    An in-memory store that reports a local data directory on disk.

    The history files live under `.kanban/`, which the in-memory repository
    does not have; this stands one in so persistence can be tested without a
    filesystem repository and a git worktree behind it.
    """

    @property
    def kanban_dir(self) -> Path | None:
        """Return the directory the history files are written to."""
        return self.root


def _make_service(root: Path) -> KanbanService:
    """Return a service over `root` holding one board of two tasks."""
    repo = _LocalRepository(root=root)
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    repo.create_column(Slug("alpha"), "todo", slug=Slug("todo"))
    svc.set_board(Slug("alpha"))

    for title in ("first", "second"):
        svc.create_task("/alpha/todo", TaskCreateParams(title=title))

    return svc


def _root() -> Path:
    """Return a fresh temporary directory to hold a store and its history files."""
    root = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    root.mkdir()
    return root


def _bar(pilot: Pilot[None], bar_type: type) -> CommandBar | FilterBar:
    """Return the board's bar of `bar_type`."""
    screen = next(s for s in pilot.app.screen_stack if isinstance(s, BoardScreen))
    return screen.query_one(bar_type)


async def _run_command(pilot: Pilot[None], line: str) -> None:
    """Type `line` into the command bar, run it, and close any output it shows."""
    await pilot.press("slash")
    await pilot.pause()
    await pilot.press(*line)
    await pilot.press("enter")
    await pilot.pause()
    await pilot.press("escape")  # dismiss the output modal, if one was pushed
    await pilot.pause()


class TestCommandBarHistory(unittest.IsolatedAsyncioTestCase):
    """↑/↓ in the command bar recall what has been run."""

    async def test_up_recalls_the_last_command(self) -> None:
        """A command that has been run comes back on ↑."""
        svc = _make_service(_root())
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await _run_command(pilot, "boards")

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("up")

            self.assertEqual(_bar(pilot, CommandBar).value, "boards")

    async def test_up_twice_reaches_the_command_before_it(self) -> None:
        """↑ keeps walking back through the commands that were run."""
        svc = _make_service(_root())
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await _run_command(pilot, "boards")
            await _run_command(pilot, "columns")

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("up", "up")

            self.assertEqual(_bar(pilot, CommandBar).value, "boards")

    async def test_down_returns_to_what_was_being_typed(self) -> None:
        """↓ at the newest end restores the half-typed line ↑ was pressed on."""
        svc = _make_service(_root())
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await _run_command(pilot, "boards")

            await pilot.press("slash")
            await pilot.pause()
            await pilot.press(*"col")
            await pilot.press("up", "down")

            self.assertEqual(_bar(pilot, CommandBar).value, "col")

    async def test_the_filter_bar_keeps_a_history_of_its_own(self) -> None:
        """Filters are recalled in the filter bar, and are not commands."""
        svc = _make_service(_root())
        async with KanbanApp(svc).run_test() as pilot:
            await pilot.pause()
            await _run_command(pilot, "boards")

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press(*"first")
            await pilot.press("enter")
            await pilot.pause()

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press("up")

            self.assertEqual(_bar(pilot, FilterBar).value, "first")


class TestBarHistoryPersistence(unittest.IsolatedAsyncioTestCase):
    """A history outlives the session that typed it."""

    async def test_a_command_is_recalled_by_the_next_run(self) -> None:
        """What was typed into the command bar is there when the TUI opens again."""
        root = _root()
        async with KanbanApp(_make_service(root)).run_test() as pilot:
            await pilot.pause()
            await _run_command(pilot, "boards")

        self.assertEqual((root / "tui-history").read_text(encoding="utf-8"), "boards\n")

        async with KanbanApp(_make_service(root)).run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()
            await pilot.press("up")

            self.assertEqual(_bar(pilot, CommandBar).value, "boards")

    async def test_the_two_bars_are_kept_in_separate_files(self) -> None:
        """A filter is not a command: each bar reads back only its own lines."""
        root = _root()
        async with KanbanApp(_make_service(root)).run_test() as pilot:
            await pilot.pause()
            await _run_command(pilot, "boards")

            await pilot.press("colon")
            await pilot.pause()
            await pilot.press(*"first")
            await pilot.press("enter")
            await pilot.pause()

        self.assertEqual((root / "tui-history").read_text(encoding="utf-8"), "boards\n")
        self.assertEqual(
            (root / "tui-filter-history").read_text(encoding="utf-8"), "first\n"
        )


if __name__ == "__main__":
    unittest.main()
