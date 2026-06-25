"""Tests for FilesystemRepository.create_task."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import Task
from storage.filesystem import FilesystemRepository


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestFilesystemCreateTask(unittest.TestCase):
    """create_task writes the correct frontmatter and registers the file in column order."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _task(self, title: str, slug: str, **kwargs) -> Task:
        now = _now()
        return Task(id=uuid4(), 
                    title=title, 
                    slug=slug, 
                    board="proj", 
                    column="todo",
                    created_at=now, 
                    updated_at=now, 
                    **kwargs)

    def _frontmatter(self, slug: str) -> dict[str, str]:
        """Read the frontmatter of a task file into a key/value dict."""
        path = self.repo.boards_dir / "proj" / "todo" / f"{slug}.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        fm: dict[str, str] = {}
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if ":" in line:
                    key, value = line.split(":", 1)
                    fm[key.strip()] = value.strip()
        return fm

    def _body(self, slug: str) -> str:
        """Read the body (content after closing frontmatter fence) of a task file."""
        path = self.repo.boards_dir / "proj" / "todo" / f"{slug}.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        end_idx = None
        if lines and lines[0].strip() == "---":
            for i in range(1, len(lines)):
                if lines[i].strip() == "---":
                    end_idx = i
                    break
        if end_idx is None:
            return ""
        return "\n".join(lines[end_idx + 1:]).strip("\n")

    # ------------------------------------------------------------------
    # Filename
    # ------------------------------------------------------------------

    def test_file_created_at_expected_path(self) -> None:
        """File is created at boards/<board>/<column>/<filename>.md."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        path = self.repo.boards_dir / "proj" / "todo" / "alpha.md"
        self.assertTrue(path.is_file())

    def test_filename_uses_supplied_filename_not_slug(self) -> None:
        """The file is named after the filename argument, not task.slug."""
        task = self._task("Alpha", "different-slug")
        self.repo.create_task(task, "alpha")
        self.assertTrue((self.repo.boards_dir / "proj" / "todo" / "alpha.md").is_file())
        self.assertFalse((self.repo.boards_dir / "proj" / "todo" / "different-slug.md").exists())

    # ------------------------------------------------------------------
    # Required frontmatter fields
    # ------------------------------------------------------------------

    def test_id_written_to_frontmatter(self) -> None:
        """The task UUID is written to the frontmatter as 'id'."""
        task = self._task("Alpha", "alpha")
        self.repo.create_task(task, "alpha")
        fm = self._frontmatter("alpha")
        self.assertEqual(fm["id"], str(task.id))

    def test_title_written_to_frontmatter(self) -> None:
        """The task title is written to the frontmatter."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        fm = self._frontmatter("alpha")
        self.assertEqual(fm["title"], "Alpha")

    def test_slug_written_to_frontmatter(self) -> None:
        """The task slug is written to the frontmatter."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        fm = self._frontmatter("alpha")
        self.assertEqual(fm["slug"], "alpha")

    def test_created_at_written_to_frontmatter(self) -> None:
        """created_at is present in the frontmatter."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        fm = self._frontmatter("alpha")
        self.assertIn("created_at", fm)
        self.assertTrue(fm["created_at"])

    def test_updated_at_written_to_frontmatter(self) -> None:
        """updated_at is present in the frontmatter."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        fm = self._frontmatter("alpha")
        self.assertIn("updated_at", fm)
        self.assertTrue(fm["updated_at"])

    # ------------------------------------------------------------------
    # Optional frontmatter fields
    # ------------------------------------------------------------------

    def test_priority_written_when_set(self) -> None:
        """priority appears in frontmatter when supplied."""
        self.repo.create_task(self._task("Alpha", "alpha", priority="high"), "alpha")
        self.assertEqual(self._frontmatter("alpha")["priority"], "high")

    def test_priority_absent_when_not_set(self) -> None:
        """priority is omitted from frontmatter when not supplied."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("priority", self._frontmatter("alpha"))

    def test_assigned_to_written_when_set(self) -> None:
        """assigned_to appears in frontmatter when supplied."""
        self.repo.create_task(self._task("Alpha", "alpha", assigned_to="alice"), "alpha")
        self.assertEqual(self._frontmatter("alpha")["assigned_to"], "alice")

    def test_assigned_to_absent_when_not_set(self) -> None:
        """assigned_to is omitted from frontmatter when not supplied."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("assigned_to", self._frontmatter("alpha"))

    def test_tags_written_when_set(self) -> None:
        """tags appears in frontmatter when supplied."""
        self.repo.create_task(self._task("Alpha", "alpha", tags=["bug", "auth"]), "alpha")
        self.assertIn("tags", self._frontmatter("alpha"))

    def test_tags_absent_when_empty(self) -> None:
        """tags is omitted from frontmatter when the list is empty."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("tags", self._frontmatter("alpha"))

    def test_due_date_written_when_set(self) -> None:
        """due_date appears in frontmatter when supplied."""
        due = datetime(2026, 12, 31, tzinfo=timezone.utc)
        self.repo.create_task(self._task("Alpha", "alpha", due_date=due), "alpha")
        self.assertIn("due_date", self._frontmatter("alpha"))

    def test_due_date_absent_when_not_set(self) -> None:
        """due_date is omitted from frontmatter when not supplied."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("due_date", self._frontmatter("alpha"))

    def test_created_by_written_when_set(self) -> None:
        """created_by appears in frontmatter when supplied."""
        self.repo.create_task(self._task("Alpha", "alpha", created_by="mark"), "alpha")
        self.assertEqual(self._frontmatter("alpha")["created_by"], "mark")

    def test_created_by_absent_when_not_set(self) -> None:
        """created_by is omitted from frontmatter when not supplied."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("created_by", self._frontmatter("alpha"))

    # ------------------------------------------------------------------
    # Fields never written to frontmatter
    # ------------------------------------------------------------------

    def test_board_not_in_frontmatter(self) -> None:
        """The task's board is not written to the frontmatter."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("board", self._frontmatter("alpha"))

    def test_column_not_in_frontmatter(self) -> None:
        """The task's column is not written to the frontmatter."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertNotIn("column", self._frontmatter("alpha"))

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def test_body_written_after_frontmatter(self) -> None:
        """The task body appears after the closing frontmatter fence."""
        self.repo.create_task(self._task("Alpha", "alpha", body="Some notes here."), "alpha")
        self.assertEqual(self._body("alpha"), "Some notes here.")

    def test_body_absent_when_not_set(self) -> None:
        """No body content is written when task.body is empty."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.assertEqual(self._body("alpha"), "")

    # ------------------------------------------------------------------
    # Column order and return value
    # ------------------------------------------------------------------

    def test_task_added_to_column_order(self) -> None:
        """Created task appears in the column task order."""
        self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        tasks = self.repo.get_tasks(board="proj", column="todo")
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0].slug, "alpha")

    def test_returns_task_with_correct_id(self) -> None:
        """create_task returns a Task whose id matches the input."""
        task = self._task("Alpha", "alpha")
        result = self.repo.create_task(task, "alpha")
        self.assertEqual(result.id, task.id)

    def test_returns_task_with_correct_location(self) -> None:
        """create_task returns a Task with board and column set from the file's location."""
        task = self._task("Alpha", "alpha")
        result = self.repo.create_task(task, "alpha")
        self.assertEqual(result.board, "proj")
        self.assertEqual(result.column, "todo")


if __name__ == "__main__":
    unittest.main()
