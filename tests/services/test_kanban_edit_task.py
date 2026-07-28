"""Tests for KanbanService.edit_task, which should only edit the task body."""

from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

from kanban.models import Priority
from kanban.services.git import GitService
from kanban.services.kanban import KanbanService, TaskCreateParams, TaskUpdateParams
from kanban.storage.memory import InMemoryRepository


def _write_body(new_body: str):
    """Return a subprocess.run side_effect that overwrites the temp file
    passed to the editor with `new_body`.
    """

    def side_effect(cmd, *args, **kwargs):
        tmp_path = cmd[-1]
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(new_body)
        return None

    return side_effect


class TestKanbanServiceEditTaskBodyOnly(unittest.TestCase):
    """`edit_task` opens only the body in the editor and preserves frontmatter."""

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

        # A task with a rich set of frontmatter fields to verify preservation.
        due = datetime(2026, 6, 30, tzinfo=timezone.utc)
        self.created = self.svc.create_task(
            "alpha/todo",
            TaskCreateParams(
                title="Fix login",
                assigned_to="alice",
                priority=Priority.HIGH,
                tags=["bug", "auth"],
                due_date=due,
                created_by="mark",
            ),
        )
        # Give it an initial body via update so we exercise a real starting body.
        self.svc.repository.update_task(
            self._with_body(self.created, "original body"),
            slug=self.created.slug,
        )

    def _with_body(self, task, body: str):
        task.body = body
        return task

    @patch("kanban.services.kanban.subprocess.run")
    def test_editor_receives_only_the_body(self, mock_run: MagicMock) -> None:
        """The editor's temp file contains just the task body, no frontmatter."""
        captured: dict[str, str] = {}

        def side_effect(cmd, *args, **kwargs):
            tmp_path = cmd[-1]
            with open(tmp_path, "r", encoding="utf-8") as f:
                captured["content"] = f.read()
            return None

        mock_run.side_effect = side_effect

        self.svc.edit_task(Path("alpha/todo/fix-login"))

        self.assertEqual(captured["content"], "original body")
        self.assertNotIn("---", captured["content"])
        self.assertNotIn("title:", captured["content"])

    @patch("kanban.services.kanban.subprocess.run")
    def test_body_is_updated_to_edited_content(self, mock_run: MagicMock) -> None:
        """The task body reflects whatever the editor wrote to the temp file."""
        mock_run.side_effect = _write_body("brand new body\n\nwith paragraphs")

        edited = self.svc.edit_task(Path("alpha/todo/fix-login"))

        self.assertEqual(edited.body, "brand new body\n\nwith paragraphs")

    @patch("kanban.services.kanban.subprocess.run")
    def test_frontmatter_is_preserved(self, mock_run: MagicMock) -> None:
        """All non-body task fields survive the edit unchanged."""
        mock_run.side_effect = _write_body("brand new body")

        edited = self.svc.edit_task(Path("alpha/todo/fix-login"))

        self.assertEqual(edited.id, self.created.id)
        self.assertEqual(edited.title, self.created.title)
        self.assertEqual(edited.slug, self.created.slug)
        self.assertEqual(edited.board, self.created.board)
        self.assertEqual(edited.column, self.created.column)
        self.assertEqual(edited.assigned_to, self.created.assigned_to)
        self.assertEqual(edited.priority, self.created.priority)
        self.assertEqual(edited.tags, self.created.tags)
        self.assertEqual(edited.due_date, self.created.due_date)
        self.assertEqual(edited.created_by, self.created.created_by)

    @patch("kanban.services.kanban.subprocess.run")
    def test_frontmatter_preserved_when_body_content_looks_like_frontmatter(
        self, mock_run: MagicMock
    ) -> None:
        """A body containing '---' delimiters and 'key: value' lines is treated
        as body text, not as frontmatter to be parsed.
        """
        payload = "---\ntitle: HACKED\n---\nbody text"
        mock_run.side_effect = _write_body(payload)

        edited = self.svc.edit_task(Path("alpha/todo/fix-login"))

        self.assertEqual(edited.title, self.created.title)
        self.assertEqual(edited.body, payload)


if __name__ == "__main__":
    unittest.main()
