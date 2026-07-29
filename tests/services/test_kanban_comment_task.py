"""Tests for KanbanService.comment_task."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams, _append_comment
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
			git_service=GitService(),
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


class TestAppendCommentHelper(unittest.TestCase):
	"""_append_comment produces the correct body layout."""

	def test_empty_body_produces_heading_and_comment(self) -> None:
		"""An empty body becomes a `# Comments` heading followed by the comment."""
		self.assertEqual(_append_comment("", "hi"), "# Comments\n\nhi")

	def test_body_without_heading_adds_heading(self) -> None:
		"""A non-empty body without the heading gets the heading appended before the comment."""
		result = _append_comment("# Description\n\nSome text.", "hi")
		self.assertEqual(result, "# Description\n\nSome text.\n\n# Comments\n\nhi")

	def test_body_with_heading_appends_only_comment(self) -> None:
		"""A body already containing the heading only receives the new comment."""
		body = "# Comments\n\nfirst"
		result = _append_comment(body, "second")
		self.assertEqual(result, "# Comments\n\nfirst\n\nsecond")

	def test_trailing_whitespace_is_stripped_from_body(self) -> None:
		"""Trailing whitespace in the original body is trimmed before appending."""
		body = "# Description\n\nSome text.\n\n\n"
		result = _append_comment(body, "hi")
		self.assertEqual(result, "# Description\n\nSome text.\n\n# Comments\n\nhi")


if __name__ == "__main__":
	unittest.main()
