"""Tests for Tab pressed twice on an argument nothing has been typed for.

The second press fills in the card the user has selected, so a command aimed at
it need not be typed out.  These tests mount a bar on its own and drive
`action_complete` with a stub completer, so what is under test is the bar's
handling of the repeat alone.
"""

from __future__ import annotations

import unittest

from textual.app import App, ComposeResult

from kanban.tui.widgets.bars import DOUBLE_TAB_TIMEOUT, CommandBar


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


def _prepare(bar: CommandBar, line: str, candidates: list[str], selected: str | None) -> None:
    """Point `bar` at `candidates` and `selected`, with `line` typed into it."""
    bar.completer = StubCompleter(candidates)
    bar.selected_task = lambda: selected
    bar.value = line
    bar.cursor_position = len(line)


class TestRepeatedTab(unittest.IsolatedAsyncioTestCase):
    """A second Tab in quick succession fills in the selected task."""

    async def test_the_selection_is_filled_in(self) -> None:
        """Tabbing twice on an empty task argument completes it with the selected slug."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view ", ["fix-login-bug", "write-api-docs"], "write-api-docs")

            bar.action_complete()
            bar.action_complete()

            self.assertEqual(bar.value, "view write-api-docs ")

    async def test_the_filled_in_slug_is_settled_with_a_space(self) -> None:
        """The cursor lands past the slug, ready for whatever the command takes next."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "move ", ["fix-login-bug", "write-api-docs"], "fix-login-bug")

            bar.action_complete()
            bar.action_complete()

            self.assertEqual(bar.cursor_position, len(bar.value))

    async def test_a_single_tab_leaves_the_line_alone(self) -> None:
        """One press offers the candidates as before, without choosing between them."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view ", ["fix-login-bug", "write-api-docs"], "write-api-docs")

            bar.action_complete()

            self.assertEqual(bar.value, "view ")

    async def test_a_third_tab_does_not_fill_the_slug_in_again(self) -> None:
        """The pair of presses is spent, so the one after it is a first press."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view ", ["fix-login-bug", "write-api-docs"], "write-api-docs")

            bar.action_complete()
            bar.action_complete()
            bar.action_complete()

            self.assertEqual(bar.value, "view write-api-docs ")


class TestWhenTheRepeatDoesNotApply(unittest.IsolatedAsyncioTestCase):
    """Everything else completes as it did before."""

    async def test_a_slow_second_tab_is_not_a_repeat(self) -> None:
        """Pressing Tab again after a pause offers the candidates rather than the selection."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view ", ["fix-login-bug", "write-api-docs"], "write-api-docs")

            bar.action_complete()
            bar._tabbed_at -= DOUBLE_TAB_TIMEOUT + 1
            bar.action_complete()

            self.assertEqual(bar.value, "view ")

    async def test_a_partly_typed_slug_is_left_to_the_candidates(self) -> None:
        """With something typed for the argument the repeat completes it, not the selection."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view fix", ["fix-login-bug", "fix-nav"], "write-api-docs")

            bar.action_complete()
            bar.action_complete()

            self.assertEqual(bar.value, "view fix-")

    async def test_an_argument_the_selection_does_not_fit_is_untouched(self) -> None:
        """A selected task is not offered where columns are what is asked for."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "move fix-login-bug ", ["todo", "done"], "write-api-docs")

            bar.action_complete()
            bar.action_complete()

            self.assertEqual(bar.value, "move fix-login-bug ")

    async def test_no_selection_completes_as_before(self) -> None:
        """A bar with nothing selected behind it treats the repeat as a plain Tab."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view ", ["fix-login-bug", "write-api-docs"], None)

            bar.action_complete()
            bar.action_complete()

            self.assertEqual(bar.value, "view ")

    async def test_a_lone_candidate_is_still_completed(self) -> None:
        """One candidate settles the token on the first press, selection or not."""
        async with _BarApp().run_test() as pilot:
            bar = pilot.app.query_one(CommandBar)
            _prepare(bar, "view ", ["fix-login-bug"], "write-api-docs")

            bar.action_complete()

            self.assertEqual(bar.value, "view fix-login-bug ")


if __name__ == "__main__":
    unittest.main()
