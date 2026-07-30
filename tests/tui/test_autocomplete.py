"""Tests for the autocomplete field's candidate matching."""

from __future__ import annotations

import unittest

from kanban.tui.widgets.autocomplete import (
    MAX_SUGGESTIONS,
    active_segment,
    entered_values,
    matching_candidates,
)

NAMES = ["alan", "alice", "alicia", "bob"]
TAGS = ["auth", "auth flow", "automation", "big bug", "bug"]


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


class TestExcludedCandidates(unittest.TestCase):
    """matching_candidates drops values the field already holds."""

    def test_excluded_values_are_not_offered(self) -> None:
        """A candidate named in `exclude` is left out of the matches."""
        self.assertEqual(
            matching_candidates(TAGS, "au", exclude=["auth"]),
            ["auth flow", "automation"],
        )

    def test_exclusion_applies_to_an_empty_prefix(self) -> None:
        """With nothing typed, everything but the excluded values is offered."""
        self.assertEqual(
            matching_candidates(TAGS, "", exclude=["auth flow", "bug"]),
            ["auth", "automation", "big bug"],
        )


class TestActiveSegment(unittest.TestCase):
    """active_segment locates the part of a field that is being completed."""

    def test_without_a_delimiter_the_whole_value_is_active(self) -> None:
        """A single-value field completes on its entire contents."""
        segment = active_segment("alice")
        self.assertEqual(segment.text, "alice")
        self.assertEqual(segment.start, 0)

    def test_completes_after_the_final_delimiter(self) -> None:
        """Only the entry after the last comma is being typed."""
        segment = active_segment("auth, bu", delimiter=",")
        self.assertEqual(segment.text, "bu")
        self.assertEqual(segment.start, 6)

    def test_skips_whitespace_after_the_delimiter(self) -> None:
        """The space conventionally typed after a comma is not part of the entry."""
        self.assertEqual(active_segment("auth,   bu", delimiter=",").text, "bu")

    def test_keeps_spaces_inside_the_entry(self) -> None:
        """Tags may contain spaces, so internal whitespace is preserved."""
        self.assertEqual(active_segment("auth, big b", delimiter=",").text, "big b")

    def test_trailing_space_is_part_of_the_entry(self) -> None:
        """A trailing space narrows the match to multi-word candidates."""
        self.assertEqual(active_segment("auth ", delimiter=",").text, "auth ")

    def test_empty_entry_after_a_delimiter(self) -> None:
        """A value ending in a comma is completing an empty entry."""
        segment = active_segment("auth, ", delimiter=",")
        self.assertEqual(segment.text, "")
        self.assertEqual(segment.start, 6)


class TestEnteredValues(unittest.TestCase):
    """entered_values reports the entries the user has already committed to."""

    def test_without_a_delimiter_nothing_is_committed(self) -> None:
        """A single-value field has no completed entries."""
        self.assertEqual(entered_values("alice"), [])

    def test_ignores_the_entry_being_typed(self) -> None:
        """The last entry is still in progress, so it is not reported."""
        self.assertEqual(entered_values("auth, bu", delimiter=","), ["auth"])

    def test_strips_surrounding_whitespace(self) -> None:
        """Entries are reported as they will be saved, without padding."""
        self.assertEqual(
            entered_values("auth ,  big bug , b", delimiter=","), ["auth", "big bug"]
        )

    def test_skips_empty_entries(self) -> None:
        """Stray commas do not produce empty entries."""
        self.assertEqual(entered_values("auth,, bug, ", delimiter=","), ["auth", "bug"])


class TestMatchLimit(unittest.TestCase):
    """matching_candidates caps how far the dropdown can grow."""

    def test_caps_the_number_of_suggestions(self) -> None:
        """No more than the limit is returned."""
        names = [f"user-{i}" for i in range(20)]
        self.assertEqual(len(matching_candidates(names, "user")), MAX_SUGGESTIONS)

    def test_limit_is_overridable(self) -> None:
        """Callers can ask for a shorter list."""
        self.assertEqual(matching_candidates(NAMES, "al", limit=2), ["alan", "alice"])
