"""Unit tests for parse_destination, which splits a move destination into column and board."""

from __future__ import annotations

import unittest

from kanban.models import Slug
from kanban.utils.str import parse_destination


class TestParseDestination(unittest.TestCase):
    """A destination is a bare column, or a /board/column path naming another board."""

    def test_bare_column_carries_no_board(self):
        """A single component is a column of the task's own board."""
        self.assertEqual(parse_destination("done"), (Slug("done"), None))

    def test_absolute_board_column_path(self):
        """A leading-slash path names the board and the column within it."""
        self.assertEqual(parse_destination("/other/todo"), (Slug("todo"), Slug("other")))

    def test_board_column_path_without_leading_slash(self):
        """Two components are board and column when a leading slash is not required."""
        self.assertEqual(parse_destination("other/todo"), (Slug("todo"), Slug("other")))

    def test_trailing_slash_is_ignored(self):
        """Empty components are dropped, so a trailing slash changes nothing."""
        self.assertEqual(parse_destination("/other/todo/"), (Slug("todo"), Slug("other")))

    def test_three_components_raise(self):
        """A destination deeper than board and column is rejected."""
        with self.assertRaises(ValueError):
            parse_destination("/other/todo/fix-login")

    def test_empty_destination_raises(self):
        """A destination with no components at all is rejected."""
        with self.assertRaises(ValueError):
            parse_destination("/")


class TestParseDestinationRequireAbsolute(unittest.TestCase):
    """With require_absolute, only a leading-slash path may name another board."""

    def test_bare_column_still_carries_no_board(self):
        """A single component is unaffected: it is a column of the task's own board."""
        self.assertEqual(parse_destination("done", require_absolute=True), (Slug("done"), None))

    def test_absolute_board_column_path_names_the_board(self):
        """A leading-slash path names another board as it does otherwise."""
        self.assertEqual(
            parse_destination("/other/todo", require_absolute=True),
            (Slug("todo"), Slug("other")),
        )

    def test_relative_board_column_path_raises(self):
        """Two components without a leading slash are rejected rather than read as a board."""
        with self.assertRaises(ValueError):
            parse_destination("other/todo", require_absolute=True)


if __name__ == "__main__":
    unittest.main()
