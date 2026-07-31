"""Tests for parsing the board's inline filter bar."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from kanban.models import Priority, Slug
from kanban.tui.filter_query import FilterQuery, parse_filter

from .helpers import make_task


class TestEmptyFilter(unittest.TestCase):
    """An empty bar narrows nothing."""

    def test_blank_text_is_an_empty_query(self) -> None:
        """Nothing typed means no filtering."""
        query = parse_filter("")
        assert query is not None
        self.assertTrue(query.is_empty)

    def test_whitespace_is_an_empty_query(self) -> None:
        """Whitespace alone is treated as nothing typed."""
        query = parse_filter("   ")
        assert query is not None
        self.assertTrue(query.is_empty)

    def test_empty_query_matches_every_task(self) -> None:
        """An empty query lets every task through."""
        self.assertTrue(FilterQuery().matches(make_task()))


class TestBareTerms(unittest.TestCase):
    """Words with no flag are matched against a task's text."""

    def test_matches_the_title(self) -> None:
        """A word from the title matches."""
        query = parse_filter("login")
        assert query is not None
        self.assertTrue(query.matches(make_task()))

    def test_matches_the_assignee(self) -> None:
        """A word from the assignee matches."""
        query = parse_filter("alice")
        assert query is not None
        self.assertTrue(query.matches(make_task()))

    def test_matches_a_tag(self) -> None:
        """A word from a tag matches."""
        query = parse_filter("auth")
        assert query is not None
        self.assertTrue(query.matches(make_task()))

    def test_ignores_case(self) -> None:
        """Matching is case-insensitive."""
        query = parse_filter("LOGIN")
        assert query is not None
        self.assertTrue(query.matches(make_task()))

    def test_non_matching_word(self) -> None:
        """A word appearing nowhere excludes the task."""
        query = parse_filter("zebra")
        assert query is not None
        self.assertFalse(query.matches(make_task()))

    def test_several_words_must_all_match(self) -> None:
        """Bare words are combined with and, not or."""
        query = parse_filter("login zebra")
        assert query is not None
        self.assertFalse(query.matches(make_task()))


class TestFilterFlags(unittest.TestCase):
    """The bar takes the same flags as the REPL's search command."""

    def test_tag_flag(self) -> None:
        """`-t` filters by tag."""
        query = parse_filter("-t auth")
        assert query is not None
        self.assertEqual(query.filter.tags, ["auth"])

    def test_long_tag_flag(self) -> None:
        """`--tag` is the same flag spelled out."""
        query = parse_filter("--tag auth")
        assert query is not None
        self.assertEqual(query.filter.tags, ["auth"])

    def test_repeated_tag_flag(self) -> None:
        """`-t` may be repeated."""
        query = parse_filter("-t auth -t bug")
        assert query is not None
        self.assertEqual(query.filter.tags, ["auth", "bug"])

    def test_priority_flag(self) -> None:
        """`-p` filters by priority, parsed into the enum."""
        query = parse_filter("-p high")
        assert query is not None
        self.assertEqual(query.filter.priority, Priority.HIGH)

    def test_assigned_to_flag(self) -> None:
        """`-w` filters by assignee."""
        query = parse_filter("-w alice")
        assert query is not None
        self.assertEqual(query.filter.assigned_to, "alice")

    def test_created_by_flag(self) -> None:
        """`--created-by` filters by creator."""
        query = parse_filter("--created-by mark")
        assert query is not None
        self.assertEqual(query.filter.created_by, "mark")

    def test_exclude_flag(self) -> None:
        """`-x` hides a column's tasks."""
        query = parse_filter("-x done")
        assert query is not None
        self.assertEqual(query.filter.exclude_columns, ["done"])

    def test_due_flags(self) -> None:
        """The due-date flags are parsed into datetimes."""
        query = parse_filter("--due-before 2026-06-20 --due-after 2026-06-01")
        assert query is not None
        self.assertEqual(
            query.filter.due_before, datetime(2026, 6, 20, tzinfo=timezone.utc)
        )
        self.assertEqual(
            query.filter.due_after, datetime(2026, 6, 1, tzinfo=timezone.utc)
        )


class TestCombinedQuery(unittest.TestCase):
    """Text and flags narrow together."""

    def test_text_and_flags_are_split(self) -> None:
        """Bare words become terms and flags become the filter."""
        query = parse_filter("login -t auth")
        assert query is not None
        self.assertEqual(query.terms, ["login"])
        self.assertEqual(query.filter.tags, ["auth"])

    def test_text_and_flag_must_both_match(self) -> None:
        """A task has to satisfy the words and the flags."""
        query = parse_filter("login -t auth")
        assert query is not None
        self.assertTrue(query.matches(make_task()))

    def test_flag_can_exclude_a_text_match(self) -> None:
        """Matching the text is not enough when a flag rules the task out."""
        query = parse_filter("login -p low")
        assert query is not None
        self.assertFalse(query.matches(make_task()))

    def test_quoted_value_keeps_its_spaces(self) -> None:
        """Quoting lets a value contain spaces, as tags may."""
        query = parse_filter('-t "big bug"')
        assert query is not None
        self.assertEqual(query.filter.tags, ["big bug"])

    def test_a_flag_alone_is_not_an_empty_query(self) -> None:
        """A query with only flags still narrows."""
        query = parse_filter("-t auth")
        assert query is not None
        self.assertFalse(query.is_empty)


class TestUnparsableInput(unittest.TestCase):
    """Half-typed input is reported rather than guessed at."""

    def test_flag_without_its_value(self) -> None:
        """A flag still waiting for its value does not parse."""
        self.assertIsNone(parse_filter("-t"))

    def test_unknown_flag(self) -> None:
        """A flag the filter does not take does not parse."""
        self.assertIsNone(parse_filter("--nonsense value"))

    def test_invalid_priority(self) -> None:
        """A priority outside the allowed set does not parse."""
        self.assertIsNone(parse_filter("-p urgent"))

    def test_unclosed_quote(self) -> None:
        """A quote left open does not parse."""
        self.assertIsNone(parse_filter('-t "big'))

    def test_invalid_date(self) -> None:
        """A date the filter cannot read does not parse."""
        self.assertIsNone(parse_filter("--due-before soon"))


class TestExcludedColumns(unittest.TestCase):
    """The exclude flag is matched against the task's column."""

    def test_task_in_an_excluded_column(self) -> None:
        """A task in an excluded column is filtered out."""
        query = parse_filter("-x todo")
        assert query is not None
        self.assertFalse(query.matches(make_task(column=Slug("todo"))))

    def test_task_in_another_column(self) -> None:
        """A task elsewhere is unaffected."""
        query = parse_filter("-x done")
        assert query is not None
        self.assertTrue(query.matches(make_task(column=Slug("todo"))))

    def test_a_column_prefix_excludes(self) -> None:
        """A partly typed column name already excludes."""
        query = parse_filter("-x to")
        assert query is not None
        self.assertFalse(query.matches(make_task(column=Slug("todo"))))


class TestPrefixMatching(unittest.TestCase):
    """Flag values match by prefix, so the bar narrows as the user types."""

    def test_partial_tag(self) -> None:
        """A tag prefix matches the tag."""
        for prefix in ("b", "bu", "bug"):
            query = parse_filter(f"-t {prefix}")
            assert query is not None
            self.assertTrue(query.matches(make_task()), prefix)

    def test_tag_prefix_that_matches_nothing(self) -> None:
        """A prefix no tag starts with excludes the task."""
        query = parse_filter("-t z")
        assert query is not None
        self.assertFalse(query.matches(make_task()))

    def test_partial_assignee(self) -> None:
        """An assignee prefix matches the assignee."""
        query = parse_filter("-w al")
        assert query is not None
        self.assertTrue(query.matches(make_task()))

    def test_assignee_prefix_is_anchored(self) -> None:
        """The prefix has to start the value, not merely appear in it."""
        query = parse_filter("-w lice")
        assert query is not None
        self.assertFalse(query.matches(make_task()))

    def test_partial_creator(self) -> None:
        """A creator prefix matches the creator."""
        query = parse_filter("--created-by ma")
        assert query is not None
        self.assertTrue(query.matches(make_task(created_by="mark")))

    def test_prefix_ignores_case(self) -> None:
        """Prefix matching is case-insensitive in both directions."""
        query = parse_filter("-w AL")
        assert query is not None
        self.assertTrue(query.matches(make_task(assigned_to="alice")))

    def test_unset_value_cannot_match_a_prefix(self) -> None:
        """A task with no assignee never satisfies an assignee filter."""
        query = parse_filter("-w a")
        assert query is not None
        self.assertFalse(query.matches(make_task(assigned_to=None)))
