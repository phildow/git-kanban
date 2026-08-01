"""Tests for the input bars' command history."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.tui.history import CommandHistory


def _history_path() -> Path:
    """Return a path in a fresh temporary directory, with no file at it yet."""
    directory = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
    directory.mkdir()
    return directory / "tui-history"


class TestCycling(unittest.TestCase):
    """↑ walks back through what was typed and ↓ walks forward again."""

    def setUp(self) -> None:
        """Start from a history of three commands, most recent last."""
        self.history = CommandHistory(None)
        for line in ("boards", "tasks todo", "create todo x"):
            self.history.append(line)

    def test_previous_starts_at_the_most_recent_entry(self) -> None:
        """The first ↑ shows the last line submitted."""
        self.assertEqual(self.history.previous(""), "create todo x")

    def test_previous_walks_back_one_entry_at_a_time(self) -> None:
        """Each ↑ moves one further back."""
        self.history.previous("")
        self.assertEqual(self.history.previous(""), "tasks todo")
        self.assertEqual(self.history.previous(""), "boards")

    def test_previous_stops_at_the_oldest_entry(self) -> None:
        """↑ at the oldest entry has nowhere to go and leaves the bar alone."""
        for _ in range(3):
            self.history.previous("")

        self.assertIsNone(self.history.previous(""))

    def test_next_walks_forward_again(self) -> None:
        """↓ retraces the steps ↑ took."""
        self.history.previous("")
        self.history.previous("")

        self.assertEqual(self.history.next(), "create todo x")

    def test_next_restores_the_draft_at_the_newest_end(self) -> None:
        """↓ past the last entry returns the line that was being typed."""
        self.history.previous("crea")

        self.assertEqual(self.history.next(), "crea")

    def test_next_on_the_draft_has_nowhere_to_go(self) -> None:
        """↓ without a preceding ↑ leaves the bar alone."""
        self.assertIsNone(self.history.next())

    def test_reset_returns_to_the_newest_end(self) -> None:
        """Clearing the bar starts ↑ from the most recent entry again."""
        self.history.previous("")
        self.history.previous("")
        self.history.reset()

        self.assertEqual(self.history.previous(""), "create todo x")

    def test_reset_forgets_the_draft(self) -> None:
        """A cleared bar has no half-typed line worth restoring."""
        self.history.previous("crea")
        self.history.reset()
        self.history.previous("")

        self.assertEqual(self.history.next(), "")

    def test_an_empty_history_has_nothing_to_show(self) -> None:
        """↑ in a bar that has never been used leaves it alone."""
        self.assertIsNone(CommandHistory(None).previous(""))


class TestRecording(unittest.TestCase):
    """What a submitted line does to the history."""

    def test_append_records_the_line(self) -> None:
        """A submitted line becomes the newest entry."""
        history = CommandHistory(None)
        history.append("boards")

        self.assertEqual(history.entries, ["boards"])

    def test_append_strips_surrounding_whitespace(self) -> None:
        """Entries are stored as the command they are, not as they were spaced."""
        history = CommandHistory(None)
        history.append("  boards  ")

        self.assertEqual(history.entries, ["boards"])

    def test_append_ignores_a_blank_line(self) -> None:
        """Submitting an empty bar records nothing."""
        history = CommandHistory(None)
        history.append("   ")

        self.assertEqual(history.entries, [])

    def test_append_ignores_an_immediate_repeat(self) -> None:
        """The same command twice in a row is one entry."""
        history = CommandHistory(None)
        history.append("boards")
        history.append("boards")

        self.assertEqual(history.entries, ["boards"])

    def test_append_keeps_a_repeat_of_an_earlier_command(self) -> None:
        """A command returned to after another is an entry of its own."""
        history = CommandHistory(None)
        history.append("boards")
        history.append("columns")
        history.append("boards")

        self.assertEqual(history.entries, ["boards", "columns", "boards"])

    def test_append_returns_the_cursor_to_the_draft(self) -> None:
        """After submitting, ↑ starts from the newest entry again."""
        history = CommandHistory(None)
        history.append("boards")
        history.previous("")
        history.append("columns")

        self.assertEqual(history.previous(""), "columns")

    def test_the_limit_drops_the_oldest_entries(self) -> None:
        """A history keeps the most recent entries and no more."""
        history = CommandHistory(None, limit=2)
        for line in ("one", "two", "three"):
            history.append(line)

        self.assertEqual(history.entries, ["two", "three"])


class TestStorage(unittest.TestCase):
    """Reading and writing the history file."""

    def test_save_then_load_round_trips_the_entries(self) -> None:
        """What one session wrote is what the next one reads."""
        path = _history_path()
        written = CommandHistory(path)
        written.append("boards")
        written.append("tasks todo")
        written.save()

        read = CommandHistory(path)
        read.load()

        self.assertEqual(read.entries, ["boards", "tasks todo"])

    def test_the_file_is_one_entry_per_line_oldest_first(self) -> None:
        """The format is plain text, as the REPL's history file is."""
        path = _history_path()
        history = CommandHistory(path)
        history.append("boards")
        history.append("columns")
        history.save()

        self.assertEqual(path.read_text(encoding="utf-8"), "boards\ncolumns\n")

    def test_load_without_a_file_leaves_the_history_empty(self) -> None:
        """A first run has nothing to read and says nothing about it."""
        history = CommandHistory(_history_path())
        history.load()

        self.assertEqual(history.entries, [])

    def test_load_applies_the_limit(self) -> None:
        """A file grown beyond the limit is read down to its most recent entries."""
        path = _history_path()
        path.write_text("one\ntwo\nthree\n", encoding="utf-8")

        history = CommandHistory(path, limit=2)
        history.load()

        self.assertEqual(history.entries, ["two", "three"])

    def test_load_ignores_blank_lines(self) -> None:
        """A file with a stray blank line still reads as its commands."""
        path = _history_path()
        path.write_text("boards\n\ncolumns\n", encoding="utf-8")

        history = CommandHistory(path)
        history.load()

        self.assertEqual(history.entries, ["boards", "columns"])

    def test_a_history_with_no_path_saves_nothing(self) -> None:
        """A repository with no local data directory keeps its history in memory."""
        history = CommandHistory(None)
        history.append("boards")
        history.save()

        self.assertEqual(history.entries, ["boards"])

    def test_save_survives_an_unwritable_path(self) -> None:
        """A history is a convenience: failing to write one is not fatal."""
        path = _history_path()
        path.mkdir()  # a directory where the file should be

        history = CommandHistory(path)
        history.append("boards")
        history.save()  # logged, not raised

    def test_load_survives_an_unreadable_file(self) -> None:
        """An unreadable history leaves the bar with an empty one."""
        path = _history_path()
        path.mkdir()

        history = CommandHistory(path)
        history.load()

        self.assertEqual(history.entries, [])


if __name__ == "__main__":
    unittest.main()
