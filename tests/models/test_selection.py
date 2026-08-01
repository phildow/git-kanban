"""Tests for the Selection model: what a visual consumer has selected."""

from __future__ import annotations

import unittest
from pathlib import Path

from kanban.models import Selection, Slug


class TestSelectionDefaults(unittest.TestCase):
    """A selection starts empty and reports itself as such."""

    def test_nothing_is_selected_by_default(self) -> None:
        """Every part of a new selection is unset."""
        selection = Selection()
        self.assertIsNone(selection.board)
        self.assertIsNone(selection.column)
        self.assertIsNone(selection.task)

    def test_a_new_selection_is_empty(self) -> None:
        """is_empty is True when nothing has been selected."""
        self.assertTrue(Selection().is_empty)

    def test_a_selected_board_is_not_empty(self) -> None:
        """A board alone is a selection."""
        self.assertFalse(Selection(board=Slug("alpha")).is_empty)


class TestSelectionPath(unittest.TestCase):
    """A selection reads as a path, as far down as it goes."""

    def test_empty_selection_has_no_path(self) -> None:
        """Nothing selected is no path, not the root."""
        self.assertIsNone(Selection().path)

    def test_board_only(self) -> None:
        """A board selection is a board path."""
        self.assertEqual(Selection(board=Slug("alpha")).path, Path("/alpha"))

    def test_board_and_column(self) -> None:
        """A column selection stops at the column."""
        selection = Selection(board=Slug("alpha"), column=Slug("todo"))
        self.assertEqual(selection.path, Path("/alpha/todo"))

    def test_the_whole_selection(self) -> None:
        """A selected task is a fully qualified task path."""
        selection = Selection(board=Slug("alpha"), column=Slug("todo"), task=Slug("fix-login"))
        self.assertEqual(selection.path, Path("/alpha/todo/fix-login"))


if __name__ == "__main__":
    unittest.main()
