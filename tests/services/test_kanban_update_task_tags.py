"""Tests that KanbanService.update_task appends tags rather than replacing them."""

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from uuid import uuid4
from unittest.mock import MagicMock

from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceUpdateTaskTags(unittest.TestCase):
	"""Verifies tag update semantics: existing tags are preserved and new tags appended."""

	def setUp(self) -> None:
		temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
		temp_dir.mkdir()
		self.repo = InMemoryRepository(root=temp_dir)
		self.svc = KanbanService(
			repository=self.repo,
			index_service=MagicMock(),
			git_service=GitService(),
		)

		self.repo.create_board("alpha", slug="alpha")
		self.repo.create_column("alpha", "todo", slug="todo")

	def test_update_task_appends_new_tags_to_existing_tags(self) -> None:
		"""New tags are added to the existing tag list, preserving prior tags."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1", tags=["bug"]))

		updated = self.svc.update_task(Path("alpha/todo/t1"), TaskUpdateParams(tags=["auth"]))

		self.assertIn("bug", updated.tags)
		self.assertIn("auth", updated.tags)

	def test_update_task_does_not_duplicate_existing_tag(self) -> None:
		"""Passing a tag that is already present does not duplicate it."""
		self.svc.create_task("alpha/todo", TaskCreateParams(title="t1", tags=["bug"]))

		updated = self.svc.update_task(Path("alpha/todo/t1"), TaskUpdateParams(tags=["bug", "auth"]))

		self.assertEqual(updated.tags.count("bug"), 1)
		self.assertIn("auth", updated.tags)


if __name__ == "__main__":
	unittest.main()
