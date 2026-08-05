"""Tests for the exit commands run from the TUI's command bar."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from textual.pilot import Pilot

from kanban.models import Slug
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService
from kanban.storage.memory import InMemoryRepository
from kanban.tui.app import KanbanApp
from kanban.tui.widgets import CommandBar, OutputPanel


def _make_service() -> KanbanService:
    """Return a service holding one board of two columns."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        git_service=GitService(),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Done", "done")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    return svc


async def _run(pilot: Pilot[None], line: str) -> None:
    """Open the command bar if needed, type `line`, and submit it."""
    bar = pilot.app.screen.query_one(CommandBar)
    if not bar.has_class("-visible"):
        await pilot.press("slash")
        await pilot.pause()

    bar.value = line
    await pilot.press("enter")
    await pilot.pause()


class TestCommandBarExit(unittest.IsolatedAsyncioTestCase):
    """The REPL's exit commands quit the app when typed into the command bar."""

    async def test_colon_q_quits(self) -> None:
        """`:q` ends the app, as it does in the REPL."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, ":q")

            self.assertFalse(pilot.app.is_running)

    async def test_exit_and_quit_also_end_the_app(self) -> None:
        """`exit` and `quit` are the same command under other names."""
        for line in ("exit", "quit"):
            with self.subTest(line=line):
                async with KanbanApp(_make_service()).run_test() as pilot:
                    await pilot.pause()
                    await _run(pilot, line)

                    self.assertFalse(pilot.app.is_running)

    async def test_a_command_named_beyond_exit_is_not_an_exit(self) -> None:
        """`exit` carrying an argument is left to the parser to reject."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "exit alpha")

            self.assertTrue(pilot.app.is_running)
            self.assertIn("unrecognized arguments", pilot.app.screen.query_one(OutputPanel).text)
