"""Tests for the panel showing what a command run from the command bar printed."""

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
from kanban.tui.widgets import CommandBar, OutputPanel


def _make_service() -> KanbanService:
    """Return a service holding one board of two columns, the first with a task."""
    repo = InMemoryRepository()
    svc = KanbanService(
        repository=repo,
        index_service=MagicMock(),
        change_tracking=ChangeTrackingService(GitChangeTracker()),
    )

    repo.create_board("alpha", slug=Slug("alpha"))
    for name, slug in (("To Do", "todo"), ("Done", "done")):
        repo.create_column(Slug("alpha"), name, slug=Slug(slug))
    svc.set_board(Slug("alpha"))

    svc.create_task("/alpha/todo", TaskCreateParams(title="first task"))

    return svc


def _panel(pilot: Pilot[None]) -> OutputPanel:
    """Return the board's output panel."""
    return pilot.app.screen.query_one(OutputPanel)


def _bar(pilot: Pilot[None]) -> CommandBar:
    """Return the board's command bar."""
    return pilot.app.screen.query_one(CommandBar)


async def _run(pilot: Pilot[None], line: str) -> None:
    """Open the command bar if needed, type `line`, and submit it."""
    if not _bar(pilot).has_class("-visible"):
        await pilot.press("slash")
        await pilot.pause()

    await pilot.press(*line)
    await pilot.press("enter")
    await pilot.pause()


class TestCommandOutputPanel(unittest.IsolatedAsyncioTestCase):
    """A command shows its output in the panel above the bar, which stays open."""

    async def test_output_is_shown_in_the_panel(self) -> None:
        """A command that prints leaves its output on screen, headed by the line."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")

            panel = _panel(pilot)
            self.assertTrue(panel.has_class("-visible"))
            self.assertIn("todo", panel.text)
            self.assertEqual(panel.border_title, "> columns")

    async def test_the_command_bar_keeps_focus(self) -> None:
        """The bar stays open, focused, and empty, ready for the next command."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")

            bar = _bar(pilot)
            self.assertTrue(bar.has_class("-visible"))
            self.assertIs(pilot.app.focused, bar)
            self.assertEqual(bar.value, "")

    async def test_a_second_command_replaces_the_output(self) -> None:
        """Output belongs to the command that produced it, not to the ones before."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")
            await _run(pilot, "boards")

            panel = _panel(pilot)
            self.assertEqual(panel.border_title, "> boards")
            self.assertIn("alpha", panel.text)
            self.assertNotIn("done", panel.text)

    async def test_a_command_that_mutates_reloads_the_board(self) -> None:
        """A command run from the bar redraws the board under it, focus untouched."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "create todo second")

            self.assertIs(pilot.app.focused, _bar(pilot))
            self.assertEqual(
                len(pilot.app.screen.svc.get_tasks("/alpha/todo")), 2
            )

    async def test_escape_closes_the_panel_with_the_bar(self) -> None:
        """The output goes with the bar that produced it, and focus returns to the board."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")
            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(_panel(pilot).has_class("-visible"))
            self.assertFalse(_bar(pilot).has_class("-visible"))
            self.assertNotIsInstance(pilot.app.focused, CommandBar)

    async def test_a_usage_error_is_shown_in_the_panel(self) -> None:
        """argparse reports a bad command line by exiting; the panel shows what it said."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "nonsuch")

            panel = _panel(pilot)
            self.assertTrue(panel.has_class("-visible"))
            self.assertIn("usage", panel.text.lower())
            self.assertTrue(_bar(pilot).has_class("-visible"))


class TestOutputPanelFocus(unittest.IsolatedAsyncioTestCase):
    """Shift+tab moves between the command bar and its output, and nowhere else."""

    async def test_shift_tab_reaches_the_panel_and_returns(self) -> None:
        """The focus cycles between the two halves of the command overlay."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")

            await pilot.press("shift+tab")
            await pilot.pause()
            self.assertIsInstance(pilot.app.focused, OutputPanel)

            await pilot.press("shift+tab")
            await pilot.pause()
            self.assertIsInstance(pilot.app.focused, CommandBar)

    async def test_shift_tab_stays_on_the_bar_with_no_output(self) -> None:
        """With nothing to read, the bar keeps the focus rather than tabbing to the board."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await pilot.press("slash")
            await pilot.pause()

            await pilot.press("shift+tab")
            await pilot.pause()

            self.assertIsInstance(pilot.app.focused, CommandBar)

    async def test_tab_does_not_leave_the_panel(self) -> None:
        """Tab is not the way back to the bar; the focus stays on the output."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")
            await pilot.press("shift+tab")
            await pilot.pause()

            await pilot.press("tab")
            await pilot.pause()

            self.assertIsInstance(pilot.app.focused, OutputPanel)

    async def test_the_board_keys_are_refused_while_the_panel_has_focus(self) -> None:
        """A card is not moved by keys pressed while the output is being read."""
        service = _make_service()
        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")
            await pilot.press("shift+tab")
            await pilot.pause()

            await pilot.press("l", "d")
            await pilot.pause()

            self.assertIsInstance(pilot.app.focused, OutputPanel)
            self.assertEqual(len(service.get_tasks("/alpha/todo")), 1)

    async def test_escape_from_the_panel_closes_the_overlay(self) -> None:
        """Escape reaches the board from the panel, taking bar and output down."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")
            await pilot.press("shift+tab")
            await pilot.pause()

            await pilot.press("escape")
            await pilot.pause()

            self.assertFalse(_panel(pilot).has_class("-visible"))
            self.assertFalse(_bar(pilot).has_class("-visible"))


class TestOutputPanelPlacement(unittest.IsolatedAsyncioTestCase):
    """The panel sits directly above the command bar and holds 80 columns."""

    async def test_the_panel_sits_above_the_command_bar(self) -> None:
        """The bar is the strip below the panel, with nothing in between."""
        async with KanbanApp(_make_service()).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "columns")

            panel = _panel(pilot).region
            bar = _bar(pilot).region

            self.assertEqual(panel.bottom, bar.y)

    async def test_shifted_arrows_scroll_the_output(self) -> None:
        """The bar holds the focus, so it is what scrolls the panel above it."""
        service = _make_service()
        for index in range(40):
            service.create_task("/alpha/todo", TaskCreateParams(title=f"task {index}"))

        async with KanbanApp(service).run_test() as pilot:
            await pilot.pause()
            await _run(pilot, "tasks")

            panel = _panel(pilot)
            self.assertGreater(panel.max_scroll_y, 0)

            await pilot.press("shift+down", "shift+down")
            await pilot.pause()

            self.assertGreater(panel.scroll_offset.y, 0)

    async def test_the_body_is_at_least_eighty_columns_wide(self) -> None:
        """A terminal too narrow for the output scrolls sideways rather than folding it."""
        async with KanbanApp(_make_service()).run_test(size=(60, 24)) as pilot:
            await pilot.pause()
            await _run(pilot, "columns")

            self.assertGreaterEqual(_panel(pilot).query_one('#output-panel-body').region.width, 80)
