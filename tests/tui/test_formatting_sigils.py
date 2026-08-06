"""Tests for the TUI's compact card sigils."""

from __future__ import annotations

import unittest
from datetime import datetime

from kanban.models import Priority
from kanban.tui.formatting import (
    format_date,
    format_timestamp,
    priority_sigil,
    priority_style,
    short_id,
)

from .helpers import make_task


class TestShortId(unittest.TestCase):
    """short_id renders the `#id` sigil."""

    def test_uses_first_eight_hex_digits(self) -> None:
        """The sigil is a hash followed by eight hex digits of the task UUID."""
        self.assertEqual(short_id(make_task()), "#a3f9c2d1")


class TestPrioritySigil(unittest.TestCase):
    """priority_sigil renders the `!PRIORITY` sigil."""

    def test_high(self) -> None:
        """High priority renders as !HIGH."""
        self.assertEqual(priority_sigil(Priority.HIGH), "!HIGH")

    def test_medium_is_abbreviated(self) -> None:
        """Medium priority is abbreviated so every sigil fits the same width."""
        self.assertEqual(priority_sigil(Priority.MEDIUM), "!MED")

    def test_low(self) -> None:
        """Low priority renders as !LOW."""
        self.assertEqual(priority_sigil(Priority.LOW), "!LOW")

    def test_none_renders_nothing(self) -> None:
        """An unset priority contributes no sigil."""
        self.assertEqual(priority_sigil(None), "")


class TestPriorityStyle(unittest.TestCase):
    """priority_style maps priorities onto semantic colours."""

    def test_high_is_red(self) -> None:
        """High priority is red."""
        self.assertEqual(priority_style(Priority.HIGH), "bold red")

    def test_none_is_dim(self) -> None:
        """An unset priority is dim."""
        self.assertEqual(priority_style(None), "dim")


class TestDateFormatting(unittest.TestCase):
    """Dates render compactly on cards and in full in the detail view, never with a time."""

    def test_format_date(self) -> None:
        """Card dates use a short month and day."""
        self.assertEqual(format_date(datetime(2026, 6, 15)), "Jun 15")

    def test_format_date_none(self) -> None:
        """An unset date renders as an empty string."""
        self.assertEqual(format_date(None), "")

    def test_format_timestamp(self) -> None:
        """Detail timestamps give the date alone, dropping the time."""
        self.assertEqual(format_timestamp(datetime(2026, 6, 15, 10, 0)), "2026-06-15")

    def test_format_timestamp_none(self) -> None:
        """An unset timestamp renders as an em dash."""
        self.assertEqual(format_timestamp(None), "—")
