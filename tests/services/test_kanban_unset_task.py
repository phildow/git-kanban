"""Tests that KanbanService.unset_task clears fields and removes tags."""

from __future__ import annotations

import tempfile
import unittest

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock

from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import GitChangeTracker
from kanban.services.kanban import (
	KanbanService,
	TaskCreateParams,
	TaskUnsetParams,
)
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceUnsetTask(unittest.TestCase):
	"""Verifies unset_task clears scalar fields and removes selected tags."""

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

		self.svc.create_task(
			"alpha/todo",
			TaskCreateParams(
				title="t1",
				assigned_to="alice",
				priority="high",
				tags=["bug", "auth", "chore"],
				due_date=datetime(2026, 6, 20, tzinfo=timezone.utc),
				created_by="mark",
			),
		)

	def test_unset_assigned_to_clears_field(self) -> None:
		"""assigned_to=True clears the assigned user."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(assigned_to=True))
		self.assertIsNone(updated.assigned_to)

	def test_unset_priority_clears_field(self) -> None:
		"""priority=True clears the priority."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(priority=True))
		self.assertIsNone(updated.priority)

	def test_unset_due_date_clears_field(self) -> None:
		"""due_date=True clears the due date."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(due_date=True))
		self.assertIsNone(updated.due_date)

	def test_unset_created_by_clears_field(self) -> None:
		"""created_by=True clears the creator name."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(created_by=True))
		self.assertIsNone(updated.created_by)

	def test_unset_tag_removes_only_named_tag(self) -> None:
		"""tags=[...] removes only the named tags and leaves the others intact."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(tags=["chore"]))
		self.assertNotIn("chore", updated.tags)
		self.assertIn("bug", updated.tags)
		self.assertIn("auth", updated.tags)

	def test_unset_tag_that_is_absent_is_noop(self) -> None:
		"""Removing a tag that is not present leaves the tag list unchanged."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(tags=["missing"]))
		self.assertEqual(set(updated.tags), {"bug", "auth", "chore"})

	def test_unset_leaves_other_fields_unchanged(self) -> None:
		"""Unsetting one field does not affect the others."""
		updated = self.svc.unset_task(Path("alpha/todo/t1"), TaskUnsetParams(assigned_to=True))
		self.assertEqual(updated.priority, "high")
		self.assertIsNotNone(updated.due_date)
		self.assertEqual(updated.created_by, "mark")
		self.assertEqual(set(updated.tags), {"bug", "auth", "chore"})


if __name__ == "__main__":
	unittest.main()
