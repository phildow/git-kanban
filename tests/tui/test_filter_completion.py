"""Tests for completing the filter bar's flags and their values."""

from __future__ import annotations

import unittest

from kanban.models import Slug
from kanban.repl.completion_engine import CompletionEngine
from kanban.tui.filter_query import build_filter_parser

from .helpers import make_board, make_column


class FakeService:
    """A stand-in data source offering fixed boards, columns, tags, and users."""

    def __init__(self) -> None:
        """Create a source with one board's worth of names."""
        self.working_board = Slug("main")

    def get_boards(self) -> list:
        """Return the available boards."""
        return [make_board()]

    def get_columns(self, board: Slug | None = None) -> list:
        """Return the active board's columns."""
        _ = board
        return [
            make_column(name="To Do", slug=Slug("todo")),
            make_column(name="Done", slug=Slug("done")),
        ]

    def get_tasks(self, *args: object, **kwargs: object) -> list:
        """Return no tasks; task names are not completed by these tests."""
        _ = args, kwargs
        return []

    def get_tags(self, board: Slug | None = None) -> list[str]:
        """Return the tags in use."""
        _ = board
        return ["auth", "bug", "docs"]

    def get_assigned_tos(self, board: Slug | None = None) -> list[str]:
        """Return the assignees in use."""
        _ = board
        return ["alice", "alicia", "bob"]


def complete(text: str) -> list[str]:
    """Return the filter bar's completions for `text`, completing at its end."""
    engine = CompletionEngine(FakeService(), build_filter_parser())  # type: ignore[arg-type]
    return engine.complete(text, len(text))


class TestFlagCompletion(unittest.TestCase):
    """A partly typed flag completes against the filter's own flags."""

    def test_unique_long_flag(self) -> None:
        """A prefix only one flag starts with completes to that flag."""
        self.assertEqual(complete("--as"), ["--assigned-to"])

    def test_ambiguous_long_flag(self) -> None:
        """A prefix several flags share offers all of them."""
        self.assertIn("--tag", complete("--t"))

    def test_every_flag_offered(self) -> None:
        """A lone dash-dash offers the filter's whole vocabulary."""
        candidates = complete("--")
        for flag in ("--tag", "--priority", "--assigned-to", "--created-by"):
            self.assertIn(flag, candidates)

    def test_unknown_prefix(self) -> None:
        """A prefix no flag starts with offers nothing."""
        self.assertEqual(complete("--zz"), [])


class TestValueCompletion(unittest.TestCase):
    """A flag's value completes against the names actually in use."""

    def test_tag_values(self) -> None:
        """`-t` completes against the board's tags."""
        self.assertEqual(complete("-t "), ["auth", "bug", "docs"])

    def test_partial_tag(self) -> None:
        """A partly typed tag narrows the candidates."""
        self.assertEqual(complete("-t a"), ["auth"])

    def test_assignee_values(self) -> None:
        """`-w` completes against the board's assignees."""
        self.assertEqual(complete("-w a"), ["alice", "alicia"])

    def test_long_assignee_flag(self) -> None:
        """The spelled-out flag completes its value too."""
        self.assertEqual(complete("--assigned-to b"), ["bob"])

    def test_priority_values(self) -> None:
        """`-p` completes against the priorities the flag allows."""
        self.assertEqual(sorted(complete("-p ")), ["high", "low", "medium"])

    def test_column_values(self) -> None:
        """`-x` completes against the active board's columns."""
        self.assertEqual(complete("-x "), ["done", "todo"])

    def test_free_text_value(self) -> None:
        """A value with no known vocabulary offers nothing."""
        self.assertEqual(complete("--due-before "), [])


class TestPartialAt(unittest.TestCase):
    """The engine reports how much of the line a candidate replaces."""

    def _engine(self) -> CompletionEngine:
        """Return an engine over the filter parser."""
        return CompletionEngine(FakeService(), build_filter_parser())  # type: ignore[arg-type]

    def test_partial_token(self) -> None:
        """A token being typed is reported in full."""
        engine = self._engine()
        self.assertEqual(engine.partial_at("-t au", 5), "au")

    def test_after_a_space(self) -> None:
        """A cursor past a space is starting a new, empty token."""
        engine = self._engine()
        self.assertEqual(engine.partial_at("-t ", 3), "")

    def test_flag_itself(self) -> None:
        """A flag being typed is the partial token."""
        engine = self._engine()
        self.assertEqual(engine.partial_at("--ta", 4), "--ta")
