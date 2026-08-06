"""Tests that KanbanService.tag_task adds a tag using set union semantics."""

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock

from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceTagTask(unittest.TestCase):
	"""Verifies tag_task adds a tag to the task without duplicating existing tags."""

	def setUp(self) -> None:
		temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
		temp_dir.mkdir()
		self.repo = InMemoryRepository(root=temp_dir)
		self.svc = KanbanService(
			repository=self.repo,
			index_service=MagicMock(),
			change_tracking=ChangeTrackingService(GitChangeTracker()),
		)

		self.repo.create_board("alpha", slug="alpha")
		self.repo.create_column("alpha", "todo", slug="todo")

	def test_tag_task_adds_tag_to_empty_task(self) -> None:
		"""tag_task adds the tag when the task has no tags."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1"))

		updated = self.svc.tag_task(Path("alpha/todo/t1"), "auth")

		self.assertEqual(updated.tags, ["auth"])

	def test_tag_task_appends_to_existing_tags(self) -> None:
		"""tag_task preserves existing tags and appends the new tag."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1", tags=["bug"]))

		updated = self.svc.tag_task(Path("alpha/todo/t1"), "auth")

		self.assertIn("bug", updated.tags)
		self.assertIn("auth", updated.tags)

	def test_tag_task_does_not_duplicate_existing_tag(self) -> None:
		"""tag_task with a tag already present leaves the tag list unchanged."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1", tags=["bug"]))

		updated = self.svc.tag_task(Path("alpha/todo/t1"), "bug")

		self.assertEqual(updated.tags.count("bug"), 1)

	def test_untag_task_removes_named_tag(self) -> None:
		"""untag_task removes only the named tag and leaves the others intact."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1", tags=["bug", "auth"]))

		updated = self.svc.untag_task(Path("alpha/todo/t1"), "bug")

		self.assertNotIn("bug", updated.tags)
		self.assertIn("auth", updated.tags)

	def test_untag_task_missing_tag_is_noop(self) -> None:
		"""untag_task with a tag that is not present leaves the tag list unchanged."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1", tags=["bug"]))

		updated = self.svc.untag_task(Path("alpha/todo/t1"), "auth")

		self.assertEqual(updated.tags, ["bug"])


if __name__ == "__main__":
	unittest.main()
