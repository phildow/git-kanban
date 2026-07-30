"""Tests for the TUI's card and header rendering."""

from __future__ import annotations

import unittest

from kanban.models import Slug
from kanban.tui.formatting import (
    board_label,
    board_subtitle,
    card_text,
    column_title,
    detail_text,
)

from .helpers import make_board, make_column, make_task


class TestCardText(unittest.TestCase):
    """card_text lays a task out over as many lines as it has metadata."""

    def test_leads_with_the_title(self) -> None:
        """The first line is the task title."""
        lines = card_text(make_task()).plain.splitlines()
        self.assertEqual(lines[0], "Fix login bug")

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
        self.assertEqual(card_text(task).plain, "Fix login bug")


class TestDenseCardText(unittest.TestCase):
    """card_text collapses to one line in dense mode."""

    def test_is_a_single_line(self) -> None:
        """Dense cards never wrap onto a second line."""
        text = card_text(make_task(), dense=True).plain
        self.assertNotIn("\n", text)

    def test_keeps_priority_and_assignee(self) -> None:
        """The dense summary still carries the priority and assignee sigils."""
        text = card_text(make_task(), dense=True).plain
        self.assertEqual(text, "Fix login bug !HIGH @alice")

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


class TestBoardLabel(unittest.TestCase):
    """board_label renders a board's row in the switcher."""

    def test_leads_with_the_name(self) -> None:
        """The display name comes first, since it is what the user chose."""
        label = board_label(make_board(column_count=4, task_count=12)).plain
        self.assertTrue(label.startswith("Main"))

    def test_includes_the_path(self) -> None:
        """The path follows the name, identifying the board the way the CLI does."""
        self.assertIn("/main", board_label(make_board()).plain)

    def test_includes_the_task_count(self) -> None:
        """The task count closes the row, unadorned."""
        label = board_label(make_board(column_count=4, task_count=12)).plain
        self.assertTrue(label.endswith("12 tasks"))

    def test_omits_the_column_count(self) -> None:
        """Columns are a detail of the board, not something to pick a board by."""
        label = board_label(make_board(column_count=4, task_count=12)).plain
        self.assertNotIn("columns", label)

    def test_pads_the_name_to_align_paths(self) -> None:
        """A name width pads the name so paths line up down the list."""
        label = board_label(make_board(), 10).plain
        self.assertTrue(label.startswith("Main      "))

    def test_name_longer_than_the_width_is_not_truncated(self) -> None:
        """Padding never shortens a name."""
        board = make_board(name="Q3 Roadmap & Planning")
        self.assertIn("Q3 Roadmap & Planning", board_label(board, 4).plain)


class TestBoardLabelAlignment(unittest.TestCase):
    """board_label lays its fields out as columns across a list of boards."""

    def _rows(self) -> list[str]:
        """Return rendered rows for boards of differing name, slug, and count widths."""
        boards = [
            make_board(name="Main", slug=Slug("main"), task_count=12),
            make_board(name="Side Quests", slug=Slug("side-quests"), task_count=0),
        ]
        name_width = max(len(board.name) for board in boards)
        path_width = max(len(board.slug) + 1 for board in boards)
        count_width = max(len(str(board.task_count)) for board in boards)

        return [
            board_label(board, name_width, path_width, count_width).plain
            for board in boards
        ]

    def test_paths_start_at_the_same_column(self) -> None:
        """Padding the name puts every path at the same offset."""
        rows = self._rows()
        self.assertEqual(rows[0].index("/main"), rows[1].index("/side-quests"))

    def test_counts_start_at_the_same_column(self) -> None:
        """Padding the path puts every count at the same offset."""
        rows = self._rows()
        self.assertEqual(rows[0].index("12 tasks"), rows[1].index("0 tasks") - 1)

    def test_counts_are_right_aligned(self) -> None:
        """A narrower number is padded so the word `tasks` still lines up."""
        rows = self._rows()
        self.assertEqual(rows[0].index("tasks"), rows[1].index("tasks"))


class TestDetailText(unittest.TestCase):
    """detail_text renders the metadata block of the task detail screen."""

    def test_includes_the_task_path(self) -> None:
        """The path identifies the task the same way the CLI does."""
        self.assertIn("/main/todo/fix-login-bug", detail_text(make_task()).plain)

    def test_title_and_path_are_on_separate_lines(self) -> None:
        """The title heads the block and the path sits on its own line below it."""
        lines = detail_text(make_task()).plain.splitlines()
        self.assertEqual(lines[0], "Fix login bug")
        self.assertEqual(lines[1], "/main/todo/fix-login-bug")

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
