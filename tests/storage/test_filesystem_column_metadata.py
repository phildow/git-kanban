"""Tests for column .metadata files and task sort order."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from kanban.models import Task
from kanban.storage.filesystem import FilesystemRepository


class TestFilesystemColumnMetadata(unittest.TestCase):
    """Values written with set_column_metadata can be read back with get_column_metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_column("alpha", "todo", slug="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_metadata_file_created_with_column(self) -> None:
        """create_column touches a .metadata file inside the column directory."""
        meta = self.repo.boards_dir / "alpha" / "todo" / ".metadata"
        self.assertTrue(meta.is_file())

    def test_written_value_is_readable(self) -> None:
        """A value written with set_column_metadata is returned by get_column_metadata."""
        self.repo.set_column_metadata("alpha", "todo", "display.color", "blue")
        self.assertEqual(self.repo.get_column_metadata("alpha", "todo", "display.color"), "blue")

    def test_returns_none_for_missing_key(self) -> None:
        """Returns None when the section exists but the key does not."""
        self.repo.set_column_metadata("alpha", "todo", "display.color", "blue")
        self.assertIsNone(self.repo.get_column_metadata("alpha", "todo", "display.nonexistent"))

    def test_returns_none_for_missing_section(self) -> None:
        """Returns None when neither the section nor key has been written."""
        self.assertIsNone(self.repo.get_column_metadata("alpha", "todo", "no-section.key"))

    def test_set_none_removes_key(self) -> None:
        """Setting a value to None removes the key; subsequent reads return None."""
        self.repo.set_column_metadata("alpha", "todo", "display.color", "blue")
        self.repo.set_column_metadata("alpha", "todo", "display.color", None)
        self.assertIsNone(self.repo.get_column_metadata("alpha", "todo", "display.color"))

    def test_metadata_scoped_to_column(self) -> None:
        """Metadata written for one column is not visible in another column."""
        self.repo.create_column("alpha", "done", slug="done")
        self.repo.set_column_metadata("alpha", "todo", "display.color", "blue")
        self.assertIsNone(self.repo.get_column_metadata("alpha", "done", "display.color"))

    def test_raises_for_invalid_keypath(self) -> None:
        """Raises KeyError when the keypath has no dot separator."""
        with self.assertRaises(KeyError):
            self.repo.get_column_metadata("alpha", "todo", "nodot")
        with self.assertRaises(KeyError):
            self.repo.set_column_metadata("alpha", "todo", "nodot", "value")


class TestFilesystemTaskOrder(unittest.TestCase):
    """Tasks in a column are returned in the order stored in .metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task(self, title: str, slug: str) -> Task:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return Task(id=uuid4(), 
                    title=title, 
                    slug=slug, 
                    board="proj", 
                    column="todo",
                    created_at=now,
                    updated_at=now)

    def test_tasks_returned_in_creation_order(self) -> None:
        """get_tasks returns tasks in the order they were created."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta", "Gamma"])

    def test_creation_order_persists_after_reload(self) -> None:
        """Task order survives a fresh repository instance (reads from .metadata)."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        fresh = FilesystemRepository(root=self.root)
        titles = [t.title for t in fresh.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta"])

    def test_task_order_file_contains_filenames(self) -> None:
        """tasks.order in .metadata stores .md filenames one per line."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        raw = self.repo.get_column_metadata("proj", "todo", "tasks.order")
        filenames = [f.strip() for f in raw.split("\n") if f.strip()]
        self.assertEqual(filenames, ["alpha.md", "beta.md"])

    def test_fallback_to_filesystem_sort_without_metadata(self) -> None:
        """Without .metadata, get_tasks falls back to alphabetical filesystem order."""
        col_dir = self.repo.boards_dir / "proj" / "todo"
        meta = col_dir / ".metadata"
        meta.unlink()
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        for slug in ("charlie", "alpha", "beta"):
            path = col_dir / f"{slug}.md"
            path.write_text(
                f"---\nid: {uuid4()}\ntitle: {slug}\nslug: {slug}\n"
                f"created_at: {now.isoformat()}\nupdated_at: {now.isoformat()}\n---\n",
                encoding="utf-8",
            )
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["alpha", "beta", "charlie"])


class TestFilesystemTaskOrderWithOtherMetadata(unittest.TestCase):
    """Task order (a multi-line INI value) survives reads and writes alongside other metadata."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task(self, title: str, slug: str) -> Task:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        return Task(id=uuid4(), 
                    title=title, 
                    slug=slug, 
                    board="proj", 
                    column="todo",
                    created_at=now, 
                    updated_at=now)

    def test_task_order_preserved_after_writing_other_metadata(self) -> None:
        """Task order is unchanged after an unrelated key is written to the same file."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.repo.set_column_metadata("proj", "todo", "display.color", "blue")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta"])

    def test_other_metadata_preserved_after_adding_task(self) -> None:
        """An unrelated metadata key is unchanged after a new task is created."""
        self.repo.set_column_metadata("proj", "todo", "display.color", "blue")
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.assertEqual(self.repo.get_column_metadata("proj", "todo", "display.color"), "blue")

    def test_task_order_preserved_across_multiple_write_cycles(self) -> None:
        """Task order survives interleaved writes from task creation and other metadata."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.set_column_metadata("proj", "todo", "display.color", "blue")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.repo.set_column_metadata("proj", "todo", "display.color", "green")
        self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta", "Gamma"])
        self.assertEqual(self.repo.get_column_metadata("proj", "todo", "display.color"), "green")

    def test_task_order_preserved_with_multiple_other_sections(self) -> None:
        """Task order is correct when several other sections exist in the metadata file."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.create_task(self._task("Beta", "beta"), "beta")
        self.repo.set_column_metadata("proj", "todo", "display.color", "blue")
        self.repo.set_column_metadata("proj", "todo", "access.owner", "alice")
        self.repo.set_column_metadata("proj", "todo", "limits.wip", "3")
        titles = [t.title for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(titles, ["Alpha", "Beta"])


if __name__ == "__main__":
    unittest.main()
