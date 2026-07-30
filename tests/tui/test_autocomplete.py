"""Tests for the autocomplete field's candidate matching."""

from __future__ import annotations

import unittest

from kanban.tui.widgets.autocomplete import MAX_SUGGESTIONS, matching_candidates

NAMES = ["alan", "alice", "alicia", "bob"]


class TestMatchingCandidates(unittest.TestCase):
    """matching_candidates filters the dropdown by what has been typed."""

    def test_matches_on_a_prefix(self) -> None:
        """Only candidates starting with the typed text are offered."""
        self.assertEqual(matching_candidates(NAMES, "ali"), ["alice", "alicia"])

    def test_ignores_case(self) -> None:
        """Matching is case-insensitive in both directions."""
        self.assertEqual(matching_candidates(["Alice", "bob"], "al"), ["Alice"])
        self.assertEqual(matching_candidates(["alice", "bob"], "AL"), ["alice"])

    def test_empty_text_matches_everything(self) -> None:
        """An empty field offers every candidate."""
        self.assertEqual(matching_candidates(NAMES, ""), NAMES)

    def test_omits_an_exact_match(self) -> None:
        """A candidate equal to the typed text is left out."""
        self.assertEqual(matching_candidates(NAMES, "alice"), [])

    def test_keeps_longer_candidates_past_an_exact_match(self) -> None:
        """Only the exact match drops out; longer candidates still show."""
        self.assertEqual(matching_candidates(["al", "alan"], "al"), ["alan"])

    def test_no_matches(self) -> None:
        """Text that matches nothing yields nothing."""
        self.assertEqual(matching_candidates(NAMES, "z"), [])

    def test_infix_does_not_match(self) -> None:
        """Matching is by prefix, not by substring."""
        self.assertEqual(matching_candidates(NAMES, "lic"), [])


class TestMatchLimit(unittest.TestCase):
    """matching_candidates caps how far the dropdown can grow."""

    def test_caps_the_number_of_suggestions(self) -> None:
        """No more than the limit is returned."""
        names = [f"user-{i}" for i in range(20)]
        self.assertEqual(len(matching_candidates(names, "user")), MAX_SUGGESTIONS)

    def test_limit_is_overridable(self) -> None:
        """Callers can ask for a shorter list."""
        self.assertEqual(matching_candidates(NAMES, "al", limit=2), ["alan", "alice"])
