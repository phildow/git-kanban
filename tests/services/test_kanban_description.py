"""Tests for the description helper and description handling in create/update."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock
from uuid import uuid4

from kanban.services.git import GitService
from kanban.services.kanban import (
	KanbanService,
	TaskCreateParams,
	TaskUpdateParams,
	_set_description,
)
from kanban.storage.memory import InMemoryRepository


class TestSetDescriptionHelper(unittest.TestCase):
	"""_set_description writes description content between the Description and Comments sections."""

	def test_empty_body_and_empty_description_produces_heading(self) -> None:
		"""An empty body and empty description yields just the `# Description` heading."""
		self.assertEqual(_set_description("", ""), "# Description\n\n")

	def test_empty_body_and_content_description_produces_heading_and_body(self) -> None:
		"""An empty body with content becomes a heading followed by the description."""
		self.assertEqual(_set_description("", "hello world"), "# Description\n\nhello world\n")

	def test_replaces_existing_description_content(self) -> None:
		"""Existing content under `# Description` is replaced by the new description."""
		body = "# Description\n\nold content"
		result = _set_description(body, "new content")
		self.assertEqual(result, "# Description\n\nnew content\n")

	def test_preserves_comments_section(self) -> None:
		"""A `# Comments` section following the description is preserved unchanged."""
		body = "# Description\n\nold\n\n# Comments\n\nA remark"
		result = _set_description(body, "new")
		self.assertEqual(result, "# Description\n\nnew\n\n# Comments\n\nA remark\n")

	def test_inserts_description_heading_when_missing(self) -> None:
		"""A body without a `# Description` heading gets one inserted at the top."""
		body = "# Comments\n\nA remark"
		result = _set_description(body, "new")
		self.assertEqual(result, "# Description\n\nnew\n\n# Comments\n\nA remark\n")

	def test_empty_description_leaves_only_heading(self) -> None:
		"""An empty description clears the description body, leaving the heading."""
		body = "# Description\n\nold content\n\n# Comments\n\nremark"
		result = _set_description(body, "")
		self.assertEqual(result, "# Description\n\n\n# Comments\n\nremark\n")


class TestCreateTaskWithDescription(unittest.TestCase):
	"""KanbanService.create_task writes the description into the task body."""

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

	def test_default_body_has_description_heading(self) -> None:
		"""A task created without a description still has the `# Description` heading."""
		result = self.svc.create_task("alpha/todo", TaskCreateParams(title="fix-login"))
		self.assertIn("# Description", result.body)

	def test_provided_description_is_written_to_body(self) -> None:
		"""A description passed to create_task appears under the heading."""
		result = self.svc.create_task(
			"alpha/todo",
			TaskCreateParams(title="fix-login", description="Login is broken"),
		)
		self.assertIn("# Description", result.body)
		self.assertIn("Login is broken", result.body)


class TestUpdateTaskWithDescription(unittest.TestCase):
	"""KanbanService.update_task replaces the description section when supplied."""

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

	def test_none_description_leaves_body_untouched(self) -> None:
		"""Passing description=None leaves the body unchanged."""
		before = self.svc.get_task(Path("alpha/todo/fix-login")).body
		self.svc.update_task(Path("alpha/todo/fix-login"), TaskUpdateParams(assigned_to="alice"))
		after = self.svc.get_task(Path("alpha/todo/fix-login")).body
		self.assertEqual(before, after)

	def test_sets_description_on_task_with_default_body(self) -> None:
		"""A supplied description populates the Description section."""
		result = self.svc.update_task(
			Path("alpha/todo/fix-login"),
			TaskUpdateParams(description="Login is broken"),
		)
		self.assertIn("# Description", result.body)
		self.assertIn("Login is broken", result.body)

	def test_replaces_existing_description_and_preserves_comments(self) -> None:
		"""A new description overwrites the old one but preserves the Comments section."""
		self.svc.update_task(
			Path("alpha/todo/fix-login"),
			TaskUpdateParams(description="First take"),
		)
		self.svc.comment_task(Path("alpha/todo/fix-login"), "Investigating")
		result = self.svc.update_task(
			Path("alpha/todo/fix-login"),
			TaskUpdateParams(description="Second take"),
		)
		self.assertIn("Second take", result.body)
		self.assertNotIn("First take", result.body)
		self.assertIn("# Comments", result.body)
		self.assertIn("Investigating", result.body)


class TestUnsetTaskWithDescription(unittest.TestCase):
	"""KanbanService.unset_task clears the description while preserving structure."""

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
		self.svc.create_task(
			"alpha/todo",
			TaskCreateParams(title="fix-login", description="Login is broken"),
		)

	def test_description_flag_clears_content_preserving_heading(self) -> None:
		"""unset_task with description=True removes description content but keeps the heading."""
		from kanban.services.kanban import TaskUnsetParams
		result = self.svc.unset_task(
			Path("alpha/todo/fix-login"),
			TaskUnsetParams(description=True),
		)
		self.assertIn("# Description", result.body)
		self.assertNotIn("Login is broken", result.body)

	def test_description_flag_preserves_comments(self) -> None:
		"""unset_task with description=True leaves any Comments section unchanged."""
		from kanban.services.kanban import TaskUnsetParams
		self.svc.comment_task(Path("alpha/todo/fix-login"), "Investigating")
		result = self.svc.unset_task(
			Path("alpha/todo/fix-login"),
			TaskUnsetParams(description=True),
		)
		self.assertIn("# Description", result.body)
		self.assertNotIn("Login is broken", result.body)
		self.assertIn("# Comments", result.body)
		self.assertIn("Investigating", result.body)

	def test_description_flag_false_leaves_body_untouched(self) -> None:
		"""unset_task with description=False (default) does not touch the body."""
		from kanban.services.kanban import TaskUnsetParams
		before = self.svc.get_task(Path("alpha/todo/fix-login")).body
		self.svc.unset_task(
			Path("alpha/todo/fix-login"),
			TaskUnsetParams(assigned_to=True),
		)
		after = self.svc.get_task(Path("alpha/todo/fix-login")).body
		self.assertEqual(before, after)


if __name__ == "__main__":
	unittest.main()
