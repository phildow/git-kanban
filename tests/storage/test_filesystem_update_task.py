"""Tests for FilesystemRepository.update_task."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from models import Task
from storage.filesystem import FilesystemRepository
from storage.kanban import TaskAlreadyExists, TaskNotFound


def _now() -> datetime:
    return datetime.now(timezone.utc)


class TestFilesystemUpdateTask(unittest.TestCase):
    """update_task rewrites task frontmatter and renames the file when the title changes."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.repo = FilesystemRepository(root=self.root)
        self.repo.init_storage()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")

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

    def test_file_still_exists_after_update(self) -> None:
        """File remains on disk at the same path when the title does not change."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.update_task(task)
        self.assertTrue((self.repo.boards_dir / "proj" / "todo" / "alpha.md").is_file())

    # ------------------------------------------------------------------
    # Required frontmatter fields
    # ------------------------------------------------------------------

    def test_id_preserved_in_frontmatter(self) -> None:
        """The original task UUID is unchanged in the frontmatter after update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["id"], str(task.id))

    def test_title_updated_in_frontmatter(self) -> None:
        """The new title is written to the frontmatter when it changes."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha-renamed")["title"], "Alpha Renamed")

    def test_title_unchanged_in_frontmatter(self) -> None:
        """The title in the frontmatter is unchanged when only other fields are updated."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.assigned_to = "alice"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["title"], "Alpha")

    def test_slug_updated_in_frontmatter_on_rename(self) -> None:
        """The slug in the frontmatter reflects the new title after a rename."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha-renamed")["slug"], "alpha-renamed")

    def test_slug_unchanged_in_frontmatter(self) -> None:
        """The slug in the frontmatter is unchanged when the title does not change."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.assigned_to = "alice"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["slug"], "alpha")

    def test_created_at_preserved_in_frontmatter(self) -> None:
        """created_at is not overwritten during an update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        original_created_at = self._frontmatter("alpha")["created_at"]
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["created_at"], original_created_at)

    def test_updated_at_present_in_frontmatter(self) -> None:
        """updated_at is present in the frontmatter after update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        self.repo.update_task(task)
        self.assertIn("updated_at", self._frontmatter("alpha"))

    # ------------------------------------------------------------------
    # Optional frontmatter fields — written when set
    # ------------------------------------------------------------------

    def test_assigned_to_written_to_frontmatter(self) -> None:
        """assigned_to appears in frontmatter after being set on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.assigned_to = "alice"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["assigned_to"], "alice")

    def test_priority_written_to_frontmatter(self) -> None:
        """priority appears in frontmatter after being set on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.priority = "high"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["priority"], "high")

    def test_tags_written_to_frontmatter(self) -> None:
        """tags appears in frontmatter after being set on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.tags = ["bug", "auth"]
        self.repo.update_task(task)
        self.assertIn("tags", self._frontmatter("alpha"))

    def test_due_date_written_to_frontmatter(self) -> None:
        """due_date appears in frontmatter after being set on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.due_date = datetime(2026, 12, 31, tzinfo=timezone.utc)
        self.repo.update_task(task)
        self.assertIn("due_date", self._frontmatter("alpha"))

    def test_created_by_written_to_frontmatter(self) -> None:
        """created_by appears in frontmatter after being set on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.created_by = "mark"
        self.repo.update_task(task)
        self.assertEqual(self._frontmatter("alpha")["created_by"], "mark")

    # ------------------------------------------------------------------
    # Optional frontmatter fields — absent when cleared
    # ------------------------------------------------------------------

    def test_assigned_to_absent_when_cleared(self) -> None:
        """assigned_to is omitted from frontmatter when set to None on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha", assigned_to="alice"), "alpha")
        task.assigned_to = None
        self.repo.update_task(task)
        self.assertNotIn("assigned_to", self._frontmatter("alpha"))

    def test_priority_absent_when_cleared(self) -> None:
        """priority is omitted from frontmatter when set to None on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha", priority="high"), "alpha")
        task.priority = None
        self.repo.update_task(task)
        self.assertNotIn("priority", self._frontmatter("alpha"))

    def test_tags_absent_when_cleared(self) -> None:
        """tags is omitted from frontmatter when set to an empty list on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha", tags=["bug"]), "alpha")
        task.tags = []
        self.repo.update_task(task)
        self.assertNotIn("tags", self._frontmatter("alpha"))

    def test_due_date_absent_when_cleared(self) -> None:
        """due_date is omitted from frontmatter when set to None on update."""
        due = datetime(2026, 12, 31, tzinfo=timezone.utc)
        task = self.repo.create_task(self._task("Alpha", "alpha", due_date=due), "alpha")
        task.due_date = None
        self.repo.update_task(task)
        self.assertNotIn("due_date", self._frontmatter("alpha"))

    def test_created_by_absent_when_cleared(self) -> None:
        """created_by is omitted from frontmatter when set to None on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha", created_by="mark"), "alpha")
        task.created_by = None
        self.repo.update_task(task)
        self.assertNotIn("created_by", self._frontmatter("alpha"))

    # ------------------------------------------------------------------
    # Fields never written to frontmatter
    # ------------------------------------------------------------------

    def test_board_not_in_frontmatter_after_update(self) -> None:
        """The task's board is not written to the frontmatter on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.assigned_to = "alice"
        self.repo.update_task(task)
        fm = self._frontmatter("alpha")
        self.assertNotIn("board", fm)

    def test_column_not_in_frontmatter_after_update(self) -> None:
        """The task's column is not written to the frontmatter on update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.assigned_to = "alice"
        self.repo.update_task(task)
        fm = self._frontmatter("alpha")
        self.assertNotIn("column", fm)

    def test_board_not_in_frontmatter_after_rename(self) -> None:
        """The task's board is not written to the frontmatter when the title changes."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        self.repo.update_task(task)
        fm = self._frontmatter("alpha-renamed")
        self.assertNotIn("board", fm)

    def test_column_not_in_frontmatter_after_rename(self) -> None:
        """The task's column is not written to the frontmatter when the title changes."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        self.repo.update_task(task)
        fm = self._frontmatter("alpha-renamed")
        self.assertNotIn("column", fm)

    # ------------------------------------------------------------------
    # Body
    # ------------------------------------------------------------------

    def test_body_updated_in_file(self) -> None:
        """Updated body text is written after the closing frontmatter fence."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.body = "Updated notes."
        self.repo.update_task(task)
        self.assertEqual(self._body("alpha"), "Updated notes.")

    def test_body_absent_when_cleared(self) -> None:
        """No body content appears in the file when task.body is cleared."""
        task = self.repo.create_task(self._task("Alpha", "alpha", body="Old notes."), "alpha")
        task.body = ""
        self.repo.update_task(task)
        self.assertEqual(self._body("alpha"), "")

    # ------------------------------------------------------------------
    # Return value
    # ------------------------------------------------------------------

    def test_returns_task_with_same_id(self) -> None:
        """update_task returns a Task whose id matches the original."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        updated = self.repo.update_task(task)
        self.assertEqual(updated.id, task.id)

    def test_returns_task_with_updated_title(self) -> None:
        """update_task returns a Task reflecting the new title."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        updated = self.repo.update_task(task)
        self.assertEqual(updated.title, "Alpha Renamed")

    def test_returns_task_with_updated_slug(self) -> None:
        """update_task returns a Task with the new slug after a rename."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        updated = self.repo.update_task(task)
        self.assertEqual(updated.slug, "alpha-renamed")

    def test_returns_task_with_correct_location(self) -> None:
        """update_task returns a Task with board and column from the file's location."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        updated = self.repo.update_task(task)
        self.assertEqual(updated.board, "proj")
        self.assertEqual(updated.column, "todo")

    # ------------------------------------------------------------------
    # Mutable fields and updated_at (return-value spot checks)
    # ------------------------------------------------------------------

    def test_mutable_fields_written(self) -> None:
        """Assigned_to, priority, and tags are reflected in the frontmatter after update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.assigned_to = "alice"
        task.priority = "high"
        task.tags = ["bug", "auth"]
        updated = self.repo.update_task(task)
        self.assertEqual(updated.assigned_to, "alice")
        self.assertEqual(updated.priority, "high")
        self.assertEqual(updated.tags, ["bug", "auth"])

    def test_updated_at_refreshed(self) -> None:
        """updated_at is later than the original after an update."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        updated = self.repo.update_task(task)
        self.assertGreaterEqual(updated.updated_at, task.updated_at)

    # ------------------------------------------------------------------
    # Rename — filename and order
    # ------------------------------------------------------------------

    def test_rename_new_file_exists(self) -> None:
        """After a title change the new file exists on disk."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        self.repo.update_task(task)
        self.assertTrue((self.repo.boards_dir / "proj" / "todo" / "alpha-renamed.md").is_file())

    def test_rename_old_file_gone(self) -> None:
        """After a title change the old file is removed from disk."""
        task = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        task.title = "Alpha Renamed"
        self.repo.update_task(task)
        self.assertFalse((self.repo.boards_dir / "proj" / "todo" / "alpha.md").exists())

    def test_rename_preserves_order_position(self) -> None:
        """A renamed task stays at its original position in column order."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t3 = self.repo.create_task(self._task("Gamma", "gamma"), "gamma")
        t2.title = "Beta Renamed"
        self.repo.update_task(t2)
        slugs = [t.slug for t in self.repo.get_tasks(board="proj", column="todo")]
        self.assertEqual(slugs, ["alpha", "beta-renamed", "gamma"])

    # ------------------------------------------------------------------
    # Error cases
    # ------------------------------------------------------------------

    def test_raises_task_not_found(self) -> None:
        """Raises TaskNotFound when no file matches the task's current slug."""
        phantom = self._task("Ghost", "ghost")
        with self.assertRaises(TaskNotFound):
            self.repo.update_task(phantom)

    def test_raises_task_already_exists_on_rename_collision(self) -> None:
        """Raises TaskAlreadyExists when the new title's slug collides with an existing task."""
        t1 = self.repo.create_task(self._task("Alpha", "alpha"), "alpha")
        t2 = self.repo.create_task(self._task("Beta", "beta"), "beta")
        t1.title = "Beta"
        with self.assertRaises(TaskAlreadyExists):
            self.repo.update_task(t1)


if __name__ == "__main__":
    unittest.main()
