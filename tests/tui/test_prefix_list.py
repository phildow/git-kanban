"""Tests for jumping through a list by typing the start of an entry."""

from __future__ import annotations

import time
import unittest

from rich.text import Text

from kanban.tui.widgets.prefix_list import SEARCH_TIMEOUT, PrefixList

COLUMNS = ["todo", "in-progress", "in-review", "done", "blocked"]


def make_list() -> PrefixList:
    """Return a list over the board's columns."""
    return PrefixList([(slug, Text(slug)) for slug in COLUMNS])


def type_text(columns: PrefixList, text: str) -> None:
    """Type `text` into the list, one character at a time."""
    for character in text:
        columns._set_search(columns._expired_search() + character)


class TestKeys(unittest.TestCase):
    """A PrefixList knows the key behind each row."""

    def test_keys_follow_the_entries(self) -> None:
        """The keys are the ones the list was built with, in order."""
        self.assertEqual(make_list().keys, COLUMNS)

    def test_key_at_an_index(self) -> None:
        """An index maps to the key of that row."""
        self.assertEqual(make_list().key_at(1), "in-progress")

    def test_key_out_of_range(self) -> None:
        """An index past the end has no key."""
        self.assertIsNone(make_list().key_at(99))

    def test_key_at_none(self) -> None:
        """No index means no key."""
        self.assertIsNone(make_list().key_at(None))


class TestTypeAhead(unittest.TestCase):
    """Typing jumps to the entry whose key starts with what was typed."""

    def test_single_character(self) -> None:
        """One letter jumps to the first key starting with it."""
        columns = make_list()
        type_text(columns, "d")
        self.assertEqual(columns.highlighted, COLUMNS.index("done"))

    def test_characters_accumulate(self) -> None:
        """Typing on narrows the search rather than restarting it."""
        columns = make_list()
        type_text(columns, "in-r")
        self.assertEqual(columns.search, "in-r")
        self.assertEqual(columns.highlighted, COLUMNS.index("in-review"))

    def test_first_match_wins(self) -> None:
        """A prefix several keys share picks the first of them."""
        columns = make_list()
        type_text(columns, "in")
        self.assertEqual(columns.highlighted, COLUMNS.index("in-progress"))

    def test_unmatched_character_is_dropped(self) -> None:
        """A letter that would match nothing leaves the search as it was."""
        columns = make_list()
        type_text(columns, "d")
        type_text(columns, "z")

        self.assertEqual(columns.search, "d")
        self.assertEqual(columns.highlighted, COLUMNS.index("done"))

    def test_backspace_shortens_the_search(self) -> None:
        """Removing a character searches for the shorter prefix."""
        columns = make_list()
        type_text(columns, "in-r")
        columns._set_search(columns.search[:-2])

        self.assertEqual(columns.search, "in")
        self.assertEqual(columns.highlighted, COLUMNS.index("in-progress"))

    def test_clearing_the_search(self) -> None:
        """An empty search leaves the highlight where it is."""
        columns = make_list()
        type_text(columns, "done")
        columns._set_search("")

        self.assertEqual(columns.search, "")
        self.assertEqual(columns.highlighted, COLUMNS.index("done"))


class TestShowSearch(unittest.TestCase):
    """The typed prefix is shown in the border subtitle unless it is turned off."""

    def test_search_is_shown_by_default(self) -> None:
        """The subtitle carries what has been typed."""
        columns = make_list()
        type_text(columns, "do")
        self.assertIn("do", columns.border_subtitle or "")

    def test_search_is_hidden_when_turned_off(self) -> None:
        """With show_search off the subtitle stays empty."""
        columns = PrefixList([(slug, Text(slug)) for slug in COLUMNS], show_search=False)
        type_text(columns, "do")
        self.assertFalse(columns.border_subtitle)

    def test_hidden_search_still_jumps(self) -> None:
        """Hiding the prefix only hides it — the jump still happens."""
        columns = PrefixList([(slug, Text(slug)) for slug in COLUMNS], show_search=False)
        type_text(columns, "do")
        self.assertEqual(columns.highlighted, COLUMNS.index("done"))


class TestSearchTimeout(unittest.TestCase):
    """A pause starts the next keystroke off as a fresh search."""

    def test_recent_keystrokes_accumulate(self) -> None:
        """Typed together, the letters build one prefix."""
        columns = make_list()
        type_text(columns, "do")
        self.assertEqual(columns._expired_search(), "do")

    def test_a_pause_starts_over(self) -> None:
        """After the timeout the prefix so far is abandoned."""
        columns = make_list()
        type_text(columns, "do")
        columns._searched_at = time.monotonic() - SEARCH_TIMEOUT - 1

        self.assertEqual(columns._expired_search(), "")
