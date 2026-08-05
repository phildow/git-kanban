"""Tests for how the input bars splice a chosen candidate back into the line.

The bars have no readline to work out which span a candidate replaces, so they
ask the completer for it.  These tests mount a bar on its own and drive
`action_complete` with a stub completer, so what is under test is the splice
alone.
"""

from __future__ import annotations

import unittest

from textual.app import App, ComposeResult

from kanban.tui.widgets.bars import CommandBar


class StubCompleter:
    """A completer returning fixed candidates and the fragment after the last `/`."""

    def __init__(self, candidates: list[str]) -> None:
        """Offer `candidates` for whatever is asked."""
        self._candidates = candidates

    def complete(self, line: str, cursor: int) -> list[str]:
        """Return the fixed candidates."""
        _ = line, cursor
        return self._candidates

    def partial_at(self, line: str, cursor: int) -> str:
        """Return the fragment a candidate replaces, as CompletionEngine does."""
        token = line[:cursor].split(" ")[-1]
        _, _, fragment = token.rpartition("/")
        return fragment


class _BarApp(App[None]):
    """An app holding nothing but a command bar, so the bar can be driven alone."""

    def compose(self) -> ComposeResult:
        """Mount the bar under test."""
        yield CommandBar(id="bar")


async def _completed(line: str, candidates: list[str]) -> CommandBar:
    """Return the bar after completing `line` against `candidates`."""
    async with _BarApp().run_test() as pilot:
        bar = pilot.app.query_one(CommandBar)
        bar.completer = StubCompleter(candidates)
        bar.value = line
        bar.cursor_position = len(line)
        bar.action_complete()
        return bar


class TestCandidateSplice(unittest.IsolatedAsyncioTestCase):
    """A single candidate replaces the fragment, leaving the rest of the line."""

    async def test_a_plain_token_is_replaced_whole(self) -> None:
        """A token with no slash is swapped for the candidate and settled with a space."""
        bar = await _completed("move fix-log", ["fix-login-bug"])
        self.assertEqual(bar.value, "move fix-login-bug ")

    async def test_an_absolute_destination_keeps_its_leading_slash(self) -> None:
        """The `/` that opened the destination stays put; only the board is filled in."""
        bar = await _completed("move fix-login-bug /op", ["ops/"])
        self.assertEqual(bar.value, "move fix-login-bug /ops/")

    async def test_a_board_segment_is_not_settled_with_a_space(self) -> None:
        """A candidate ending in `/` leaves the cursor against the slash for the column."""
        bar = await _completed("move fix-login-bug /op", ["ops/"])
        self.assertEqual(bar.cursor_position, len(bar.value))
        self.assertFalse(bar.value.endswith(" "))

    async def test_a_column_past_a_board_replaces_the_last_segment_alone(self) -> None:
        """The board already typed survives completing the column after it."""
        bar = await _completed("move fix-login-bug /ops/back", ["backlog"])
        self.assertEqual(bar.value, "move fix-login-bug /ops/backlog ")

    async def test_a_lone_slash_is_completed_onto(self) -> None:
        """With nothing after the slash the candidate is added to it, not swapped for it."""
        bar = await _completed("move fix-login-bug /", ["ops/"])
        self.assertEqual(bar.value, "move fix-login-bug /ops/")


class TestAmbiguousSplice(unittest.IsolatedAsyncioTestCase):
    """Several candidates are narrowed to what they agree on, and no further."""

    async def test_shared_prefix_is_filled_in(self) -> None:
        """A prefix every candidate starts with is added to the fragment."""
        bar = await _completed("move fix-login-bug /o", ["ops-one/", "ops-two/"])
        self.assertEqual(bar.value, "move fix-login-bug /ops-")

    async def test_candidates_that_share_nothing_leave_the_line_alone(self) -> None:
        """Boards with no common prefix leave the slash as it was typed."""
        bar = await _completed("move fix-login-bug /", ["my-project/", "ops/"])
        self.assertEqual(bar.value, "move fix-login-bug /")


if __name__ == "__main__":
    unittest.main()
