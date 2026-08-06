"""Tests for KanbanService.comment_task."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.change_tracking import ChangeTrackingService
from kanban.tracking import InMemoryChangeTracker
from kanban.services.kanban import CONFIG_USER_NAME, KanbanService, TaskCreateParams
from kanban.storage.memory import InMemoryRepository


class TestKanbanServiceCommentTask(unittest.TestCase):
	"""KanbanService.comment_task appends comments under a `# Comments` heading."""

	def setUp(self) -> None:
		temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
		temp_dir.mkdir()
		self.repo = InMemoryRepository(root=temp_dir)
		self.svc = KanbanService(
			repository=self.repo,
			index_service=MagicMock(),
			change_tracking=ChangeTrackingService(InMemoryChangeTracker(), self.repo),
		)
		self.repo.create_board("alpha", slug="alpha")
		self.repo.create_column("alpha", "todo", slug="todo")
		self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))

	def test_creates_comments_heading_on_empty_body(self) -> None:
		"""comment_task adds the `# Comments` heading when the body is empty."""
		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "First comment")
		self.assertIn("# Comments", result.body)
		self.assertIn("First comment", result.body)

	def test_appends_second_comment_under_existing_heading(self) -> None:
		"""comment_task appends subsequent comments under the same heading."""
		self.svc.comment_task(Path("alpha/todo/fix-login"), "First comment")
		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "Second comment")
		self.assertEqual(result.body.count("# Comments"), 1)
		self.assertIn("First comment", result.body)
		self.assertIn("Second comment", result.body)

	def test_preserves_existing_body_content(self) -> None:
		"""comment_task keeps the original body content before the heading."""
		task = self.svc.get_task(Path("alpha/todo/fix-login"))
		task.body = "# Description\n\nThe login button is broken."
		self.repo.update_task(task, slug=task.slug)

		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "Investigating")
		self.assertIn("# Description", result.body)
		self.assertIn("The login button is broken.", result.body)
		self.assertIn("# Comments", result.body)
		self.assertIn("Investigating", result.body)
		self.assertLess(result.body.index("# Description"), result.body.index("# Comments"))

	def test_returned_task_identity_matches_original(self) -> None:
		"""comment_task returns a task whose id matches the original."""
		original = self.svc.get_task(Path("alpha/todo/fix-login"))
		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "hi")
		self.assertEqual(result.id, original.id)

	def test_comment_is_filed_under_a_dated_heading(self) -> None:
		"""Each comment gets an `## YYYY-MM-DD` heading of its own."""
		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "First comment")
		today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

		self.assertIn(f"## {today}", result.body)

	def test_each_comment_gets_its_own_heading(self) -> None:
		"""A second comment is filed under a heading of its own, not the first one's."""
		self.svc.comment_task(Path("alpha/todo/fix-login"), "First comment")
		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "Second comment")

		self.assertEqual(result.body.count("## "), 2)

	def test_heading_names_the_configured_user(self) -> None:
		"""With user.name set the heading names the author with an `@`."""
		self.svc.set_config(CONFIG_USER_NAME, "philip")

		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "First comment")
		today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

		self.assertIn(f"## {today} @philip", result.body)

	def test_heading_is_the_date_alone_without_a_configured_user(self) -> None:
		"""With no user.name the heading carries no author."""
		result = self.svc.comment_task(Path("alpha/todo/fix-login"), "First comment")

		self.assertNotIn("@", result.body)


if __name__ == "__main__":
	unittest.main()
