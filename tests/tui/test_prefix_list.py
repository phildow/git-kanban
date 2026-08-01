"""Tests for jumping through a list by typing the start of an entry."""

from __future__ import annotations

import time
import unittest

from rich.text import Text
from textual import events

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


class TestReservedCharacters(unittest.TestCase):
    """Characters a screen keeps for itself are not taken for the search."""

    def _list(self) -> PrefixList:
        """Return a list that leaves `d` to whatever binds it."""
        return PrefixList([(slug, Text(slug)) for slug in COLUMNS], reserved=["d"])

    def test_reserved_character_starts_no_search(self) -> None:
        """A reserved character does not become the prefix."""
        columns = self._list()
        columns.on_key(_key_event("d"))

        self.assertEqual(columns.search, "")

    def test_reserved_character_is_left_to_bubble(self) -> None:
        """The event is not stopped, so a binding elsewhere can answer it."""
        columns = self._list()
        event = _key_event("d")
        columns.on_key(event)

        self.assertFalse(event._stop_propagation)

    def test_searched_character_is_consumed(self) -> None:
        """A character the search takes does not go on to anything else."""
        columns = self._list()
        event = _key_event("t")
        columns.on_key(event)

        self.assertTrue(event._stop_propagation)

    def test_other_characters_still_search(self) -> None:
        """Everything not reserved goes on jumping as before."""
        columns = self._list()
        columns.on_key(_key_event("t"))

        self.assertEqual(columns.selected_key, "todo")


def _key_event(character: str) -> events.Key:
    """Return a key event for `character`, as the terminal would deliver it."""
    return events.Key(key=character, character=character)


def make_grouped_list() -> PrefixList:
    """Return a list whose entries are grouped under headings."""
    return PrefixList(
        [
            (None, Text("open")),
            ("todo", Text("todo")),
            ("in-progress", Text("in-progress")),
            (None, Text("closed")),
            ("done", Text("done")),
        ]
    )


class TestHeadings(unittest.TestCase):
    """An entry with no key is a heading: shown, but not one of the choices."""

    def test_headings_are_disabled(self) -> None:
        """A keyless row cannot be chosen."""
        rows = make_grouped_list()

        self.assertTrue(rows.get_option_at_index(0).disabled)

    def test_entries_are_not_disabled(self) -> None:
        """A row with a key stays selectable."""
        rows = make_grouped_list()

        self.assertFalse(rows.get_option_at_index(1).disabled)

    def test_heading_rows_have_no_key(self) -> None:
        """The key at a heading's index is None."""
        self.assertIsNone(make_grouped_list().key_at(0))

    def test_typing_skips_headings(self) -> None:
        """A prefix matching a heading's text lands on nothing."""
        rows = make_grouped_list()
        type_text(rows, "op")

        self.assertNotEqual(rows.highlighted, 0)

    def test_typing_still_reaches_entries(self) -> None:
        """Grouping does not stop typing from jumping to an entry."""
        rows = make_grouped_list()
        type_text(rows, "d")

        self.assertEqual(rows.highlighted, 4)

    def test_first_key_index_skips_headings(self) -> None:
        """The first selectable row is the one below the first heading."""
        self.assertEqual(make_grouped_list().first_key_index, 1)

    def test_first_key_index_without_entries(self) -> None:
        """A list of headings alone has nothing to select."""
        rows = PrefixList([(None, Text("open"))])

        self.assertIsNone(rows.first_key_index)

    def test_set_entries_keeps_headings_disabled(self) -> None:
        """Rebuilding the rows preserves which of them are headings."""
        rows = make_grouped_list()
        rows.set_entries([(None, Text("open")), ("todo", Text("todo"))])

        self.assertTrue(rows.get_option_at_index(0).disabled)
        self.assertFalse(rows.get_option_at_index(1).disabled)
