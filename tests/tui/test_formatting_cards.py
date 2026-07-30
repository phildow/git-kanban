"""Tests for the TUI's card and header rendering."""

from __future__ import annotations

import unittest

from kanban.models import Slug
from kanban.tui.formatting import board_subtitle, card_text, column_title, detail_text

from .helpers import make_board, make_column, make_task


class TestCardText(unittest.TestCase):
    """card_text lays a task out over as many lines as it has metadata."""

    def test_includes_id_and_title(self) -> None:
        """The first line carries the id sigil and the title."""
        lines = card_text(make_task()).plain.splitlines()
        self.assertEqual(lines[0], "#a3f9c2d1 Fix login bug")

    def test_includes_priority_and_assignee(self) -> None:
        """Priority and assignee share the second line."""
        lines = card_text(make_task()).plain.splitlines()
        self.assertEqual(lines[1], "!HIGH  @alice")

    def test_includes_due_date(self) -> None:
        """The due date gets its own line."""
        lines = card_text(make_task()).plain.splitlines()
        self.assertEqual(lines[2], "due Jun 15")

    def test_includes_tags(self) -> None:
        """Tags render with a hash sigil on the final line."""
        lines = card_text(make_task()).plain.splitlines()
        self.assertEqual(lines[3], "#bug #auth")

    def test_omits_unset_metadata(self) -> None:
        """A task with no metadata renders as a single title line."""
        task = make_task(priority=None, assigned_to=None, due_date=None, tags=[])
        self.assertEqual(card_text(task).plain, "#a3f9c2d1 Fix login bug")


class TestDenseCardText(unittest.TestCase):
    """card_text collapses to one line in dense mode."""

    def test_is_a_single_line(self) -> None:
        """Dense cards never wrap onto a second line."""
        text = card_text(make_task(), dense=True).plain
        self.assertNotIn("\n", text)

    def test_keeps_priority_and_assignee(self) -> None:
        """The dense summary still carries the priority and assignee sigils."""
        text = card_text(make_task(), dense=True).plain
        self.assertEqual(text, "#a3f9c2d1 Fix login bug !HIGH @alice")

    def test_drops_due_date_and_tags(self) -> None:
        """The dense summary omits the due date and tags."""
        text = card_text(make_task(), dense=True).plain
        self.assertNotIn("Jun 15", text)
        self.assertNotIn("#bug", text)


class TestColumnTitle(unittest.TestCase):
    """column_title renders the column's border title."""

    def test_upper_cases_name_with_count(self) -> None:
        """The title is the upper-cased column name followed by its task count."""
        self.assertEqual(column_title(make_column(), 4), " TO DO (4) ")


class TestBoardSubtitle(unittest.TestCase):
    """board_subtitle describes the active board in the header."""

    def test_uses_supplied_counts(self) -> None:
        """The counts come from the caller so the header matches the screen."""
        self.assertEqual(
            board_subtitle(make_board(), 4, 12), "/main — 4 columns, 12 tasks"
        )

    def test_without_a_board(self) -> None:
        """With no active board the subtitle says so."""
        self.assertEqual(board_subtitle(None, 0, 0), "no board")


class TestDetailText(unittest.TestCase):
    """detail_text renders the metadata block of the task detail screen."""

    def test_includes_the_task_path(self) -> None:
        """The path identifies the task the same way the CLI does."""
        self.assertIn("/main/todo/fix-login-bug", detail_text(make_task()).plain)

    def test_labels_every_field(self) -> None:
        """Each metadata field is labelled, including the ones that are unset."""
        text = detail_text(make_task(created_by=None)).plain
        for label in ("priority", "assigned", "created by", "due", "tags"):
            self.assertIn(label, text)

    def test_unset_fields_render_as_a_dash(self) -> None:
        """Unset fields render as an em dash rather than being omitted."""
        task = make_task(priority=None, assigned_to=None, due_date=None, tags=[])
        self.assertIn("—", detail_text(task).plain)

    def test_renames_follow_the_slug(self) -> None:
        """The rendered path reflects the task's current slug."""
        task = make_task(slug=Slug("fix-logout-bug"))
        self.assertIn("/main/todo/fix-logout-bug", detail_text(task).plain)
