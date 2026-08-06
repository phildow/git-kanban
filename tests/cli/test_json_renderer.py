"""Tests confirming JSON output produced by JsonRenderer.

Each test captures stdout, parses the JSON, and asserts the expected structure
and field values.
"""

from __future__ import annotations

import io
import json
import unittest
from argparse import Namespace
from contextlib import redirect_stdout
from datetime import datetime, timezone
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from kanban.models import Board, Column, Task, UserContext
from kanban.services.kanban import Commit, KanbanStatus
from kanban.cli.json_renderer import JsonRenderer


_TASK_ID = UUID("a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d")
_CREATED_AT = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
_UPDATED_AT = datetime(2026, 1, 2, 9, 0, 0, tzinfo=timezone.utc)


def _args(**kwargs) -> Namespace:
    return Namespace(**kwargs)


def _mock_render_service() -> MagicMock:
    """Return a `RenderService` mock that resolves slugs into `Board`/`Column`
    instances derived from the requested slug/path.
    """
    mock = MagicMock()
    mock.board_for_slug.side_effect = lambda slug: _board(name=slug, slug=slug)
    mock.column_for_path.side_effect = lambda path: _column(
        name=path.name, slug=path.name, board=path.parent.name.lstrip("/")
    )
    return mock


def _capture(fn) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        fn()
    return buf.getvalue().strip()


def _task(**kwargs) -> Task:
    defaults = dict(
        id=_TASK_ID,
        title="Fix login bug",
        slug="fix-login-bug",
        board="main",
        column="todo",
        created_at=_CREATED_AT,
        updated_at=_UPDATED_AT,
    )
    defaults.update(kwargs)
    return Task(**defaults)


def _board(name: str = "main", slug: str = "main", column_count: int = 4, task_count: int = 0, archived_task_count: int = 0, id: UUID | None = None) -> Board:
    return Board(id=id or uuid4(), name=name, slug=slug, column_count=column_count, task_count=task_count, archived_task_count=archived_task_count)


def _column(name: str = "todo", board: str = "main", position: int = 0, slug: str = "", id: UUID | None = None) -> Column:
    return Column(id=id or uuid4(), name=name, slug=slug, board=board, position=position)


class TestJsonRendererBoards(unittest.TestCase):
    """JSON output for board-related render methods."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())

    def test_board_list_is_array(self) -> None:
        """render_board_list emits a JSON array."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("alpha"), _board("beta")]))
        self.assertIsInstance(json.loads(out), list)

    def test_board_list_length(self) -> None:
        """render_board_list array length matches input."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("alpha"), _board("beta")]))
        self.assertEqual(len(json.loads(out)), 2)

    def test_board_list_name_field(self) -> None:
        """Each board entry contains the correct name."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("alpha")]))
        self.assertEqual(json.loads(out)[0]["name"], "alpha")

    def test_board_list_slug_field(self) -> None:
        """Each board entry contains the slug."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("My Project", "my-project")]))
        self.assertEqual(json.loads(out)[0]["slug"], "my-project")

    def test_board_list_id_field(self) -> None:
        """Each board entry contains its id as a string."""
        board_id = uuid4()
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("alpha", id=board_id)]))
        self.assertEqual(json.loads(out)[0]["id"], str(board_id))

    def test_board_info_id_field(self) -> None:
        """render_board_info emits the board id."""
        board_id = uuid4()
        out = _capture(lambda: self.r.render_board_info(_args(), _board("proj", id=board_id)))
        self.assertEqual(json.loads(out)["id"], str(board_id))

    def test_board_list_path_field_present(self) -> None:
        """Each board entry contains a path field."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("alpha")]))
        self.assertIn("path", json.loads(out)[0])

    def test_board_list_column_count_field(self) -> None:
        """Each board entry contains the correct column_count."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board("alpha", "alpha", 4)]))
        self.assertEqual(json.loads(out)[0]["column_count"], 4)

    def test_board_list_task_count_fields(self) -> None:
        """Each board entry reports its task_count and archived_task_count apart."""
        board = _board("alpha", "alpha", 4, task_count=7, archived_task_count=3)
        out = _capture(lambda: self.r.render_board_list(_args(), [board]))
        obj = json.loads(out)[0]
        self.assertEqual(obj["task_count"], 7)
        self.assertEqual(obj["archived_task_count"], 3)

    def test_board_list_empty_array(self) -> None:
        """render_board_list emits an empty JSON array for an empty list."""
        out = _capture(lambda: self.r.render_board_list(_args(), []))
        self.assertEqual(json.loads(out), [])

    def test_board_create_name_field(self) -> None:
        """render_board_create emits a JSON object with the board name."""
        out = _capture(lambda: self.r.render_board_create(_args(), _board("proj")))
        self.assertEqual(json.loads(out)["name"], "proj")

    def test_board_create_slug_field(self) -> None:
        """render_board_create emits the board slug."""
        out = _capture(lambda: self.r.render_board_create(_args(), _board( "My Project", "my-project")))
        self.assertEqual(json.loads(out)["slug"], "my-project")

    def test_board_info_name_field(self) -> None:
        """render_board_info emits a JSON object with the board name."""
        out = _capture(lambda: self.r.render_board_info(_args(), _board("proj")))
        self.assertEqual(json.loads(out)["name"], "proj")

    def test_board_info_slug_field(self) -> None:
        """render_board_info emits the board slug."""
        out = _capture(lambda: self.r.render_board_info(_args(), _board("My Project", "my-project")))
        self.assertEqual(json.loads(out)["slug"], "my-project")

    def test_board_info_path_field_present(self) -> None:
        """render_board_info emits a path field."""
        out = _capture(lambda: self.r.render_board_info(_args(), _board("proj")))
        self.assertIn("path", json.loads(out))

    def test_board_rename_name_field(self) -> None:
        """render_board_rename emits a JSON object with the new board name."""
        out = _capture(lambda: self.r.render_board_rename(_args(), _board("new-name")))
        self.assertEqual(json.loads(out)["name"], "new-name")

    def test_board_rename_slug_field(self) -> None:
        """render_board_rename emits the new board slug."""
        out = _capture(lambda: self.r.render_board_rename(_args(), _board("New Name", "new-name")))
        self.assertEqual(json.loads(out)["slug"], "new-name")

    def test_board_delete_emits_the_board(self) -> None:
        """render_board_delete emits the deleted board's own representation."""
        out = _capture(lambda: self.r.render_board_delete(_args(board="proj"), _board("proj", "proj")))
        obj = json.loads(out)
        self.assertEqual(obj["name"], "proj")
        self.assertEqual(obj["path"], "/proj")

    def test_board_delete_deleted_field(self) -> None:
        """render_board_delete carries the board's deleted flag."""
        board = _board("proj", "proj")
        board.deleted = True
        out = _capture(lambda: self.r.render_board_delete(_args(board="proj"), board))
        self.assertTrue(json.loads(out)["deleted"])

    def test_board_list_deleted_field_is_false(self) -> None:
        """A board that was not deleted reports deleted as false."""
        out = _capture(lambda: self.r.render_board_list(_args(), [_board()]))
        self.assertFalse(json.loads(out)[0]["deleted"])


class TestJsonRendererColumns(unittest.TestCase):
    """JSON output for column-related render methods."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())

    def test_column_list_is_array(self) -> None:
        """render_column_list emits a JSON array."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("todo"), _column("done")]))
        self.assertIsInstance(json.loads(out), list)

    def test_column_list_name_field(self) -> None:
        """Each column entry contains the correct name."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("todo", "main", 0)]))
        self.assertEqual(json.loads(out)[0]["name"], "todo")

    def test_column_list_board_field(self) -> None:
        """Each column entry contains the owning board as a nested ref dict."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("todo", "main", 0)]))
        self.assertEqual(json.loads(out)[0]["board"]["slug"], "main")

    def test_column_list_position_field(self) -> None:
        """Each column entry contains the zero-based position."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("done", "main", 2)]))
        self.assertEqual(json.loads(out)[0]["position"], 2)

    def test_column_list_slug_field(self) -> None:
        """Each column entry contains the slug."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("In Progress", "main", 1, "in-progress")]))
        self.assertEqual(json.loads(out)[0]["slug"], "in-progress")

    def test_column_list_id_field(self) -> None:
        """Each column entry contains its id as a string."""
        column_id = uuid4()
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("todo", "main", 0, id=column_id)]))
        self.assertEqual(json.loads(out)[0]["id"], str(column_id))

    def test_column_list_board_ref_id_field(self) -> None:
        """The nested board ref of a column entry contains an id."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("todo", "main", 0)]))
        self.assertIn("id", json.loads(out)[0]["board"])

    def test_column_info_id_field(self) -> None:
        """render_column_info emits the column id."""
        column_id = uuid4()
        out = _capture(lambda: self.r.render_column_info(_args(), _column("todo", "main", 0, id=column_id)))
        self.assertEqual(json.loads(out)["id"], str(column_id))

    def test_column_list_path_field_present(self) -> None:
        """Each column entry contains a path field."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column("todo", "main", 0)]))
        self.assertIn("path", json.loads(out)[0])

    def test_column_list_empty_array(self) -> None:
        """render_column_list emits an empty JSON array for an empty list."""
        out = _capture(lambda: self.r.render_column_list(_args(), []))
        self.assertEqual(json.loads(out), [])

    def test_column_info_name_field(self) -> None:
        """render_column_info emits a JSON object with the column name."""
        out = _capture(lambda: self.r.render_column_info(_args(), _column("todo", "main", 0)))
        self.assertEqual(json.loads(out)["name"], "todo")

    def test_column_info_board_field(self) -> None:
        """render_column_info emits the owning board as a nested ref dict."""
        out = _capture(lambda: self.r.render_column_info(_args(), _column("todo", "main", 0)))
        self.assertEqual(json.loads(out)["board"]["slug"], "main")

    def test_column_info_path_field_present(self) -> None:
        """render_column_info emits a path field."""
        out = _capture(lambda: self.r.render_column_info(_args(), _column("todo", "main", 0)))
        self.assertIn("path", json.loads(out))

    def test_column_create_name_field(self) -> None:
        """render_column_create emits a JSON object with the column name."""
        out = _capture(lambda: self.r.render_column_create(_args(), _column("review", "proj", 1)))
        self.assertEqual(json.loads(out)["name"], "review")

    def test_column_create_slug_field(self) -> None:
        """render_column_create emits the slug."""
        out = _capture(lambda: self.r.render_column_create(_args(), _column("In Review", "proj", 1, "in-review")))
        self.assertEqual(json.loads(out)["slug"], "in-review")

    def test_column_delete_emits_the_column(self) -> None:
        """render_column_delete emits the deleted column's own representation."""
        out = _capture(lambda: self.r.render_column_delete(_args(path="main/todo"), _column("To Do", "main", 0, "todo")))
        obj = json.loads(out)
        self.assertEqual(obj["name"], "To Do")
        self.assertEqual(obj["path"], "/main/todo")

    def test_column_delete_deleted_field(self) -> None:
        """render_column_delete carries the column's deleted flag."""
        column = _column("To Do", "main", 0, "todo")
        column.deleted = True
        out = _capture(lambda: self.r.render_column_delete(_args(path="main/todo"), column))
        self.assertTrue(json.loads(out)["deleted"])

    def test_column_list_deleted_field_is_false(self) -> None:
        """A column that was not deleted reports deleted as false."""
        out = _capture(lambda: self.r.render_column_list(_args(), [_column()]))
        self.assertFalse(json.loads(out)[0]["deleted"])


class TestJsonRendererTasks(unittest.TestCase):
    """JSON output for task-related render methods."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())

    def test_task_list_is_array(self) -> None:
        """render_task_list emits a JSON array."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task(), _task(slug="second", title="Second")]))
        self.assertIsInstance(json.loads(out), list)

    def test_task_list_length(self) -> None:
        """render_task_list array length matches input."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task(), _task(id=uuid4(), slug="t2", title="T2")]))
        self.assertEqual(len(json.loads(out)), 2)

    def test_task_list_title_field(self) -> None:
        """Each task entry contains the title."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertEqual(json.loads(out)[0]["title"], "Fix login bug")

    def test_task_list_slug_field(self) -> None:
        """Each task entry contains the slug."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertEqual(json.loads(out)[0]["slug"], "fix-login-bug")

    def test_task_list_id_field(self) -> None:
        """Each task entry contains its id as a string."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertEqual(json.loads(out)[0]["id"], str(_TASK_ID))

    def test_task_list_board_ref_id_field(self) -> None:
        """The nested board ref of a task entry contains an id."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertIn("id", json.loads(out)[0]["board"])

    def test_task_list_column_ref_id_field(self) -> None:
        """The nested column ref of a task entry contains an id."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertIn("id", json.loads(out)[0]["column"])

    def test_task_view_id_field(self) -> None:
        """render_task_view emits the task id."""
        out = _capture(lambda: self.r.render_task_view(_args(), _task()))
        self.assertEqual(json.loads(out)["id"], str(_TASK_ID))

    def test_task_list_path_field_present(self) -> None:
        """Each task entry contains a path field."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertIn("path", json.loads(out)[0])

    def test_task_list_board_field(self) -> None:
        """Each task entry contains the board as a nested ref dict."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertEqual(json.loads(out)[0]["board"]["slug"], "main")

    def test_task_list_column_field(self) -> None:
        """Each task entry contains the column as a nested ref dict."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertEqual(json.loads(out)[0]["column"]["slug"], "todo")

    def test_task_list_optional_fields_present(self) -> None:
        """Optional fields are present in each task entry (may be null)."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        entry = json.loads(out)[0]
        for field in ("assigned_to", "priority", "due_date", "tags", "created_by"):
            self.assertIn(field, entry)

    def test_task_list_optional_field_values(self) -> None:
        """Optional fields carry their values when set."""
        due = datetime(2026, 6, 30, tzinfo=timezone.utc)
        t = _task(assigned_to="alice", priority="high", tags=["bug"], due_date=due, created_by="mark")
        out = _capture(lambda: self.r.render_task_list(_args(), [t]))
        entry = json.loads(out)[0]
        self.assertEqual(entry["assigned_to"], "alice")
        self.assertEqual(entry["priority"], "high")
        self.assertEqual(entry["tags"], ["bug"])
        self.assertEqual(entry["created_by"], "mark")
        self.assertIsNotNone(entry["due_date"])

    def test_task_list_excludes_timestamps(self) -> None:
        """Task list entries do not include created_at, updated_at, or body."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        entry = json.loads(out)[0]
        for field in ("created_at", "updated_at", "body"):
            self.assertNotIn(field, entry)

    def test_task_list_empty_array(self) -> None:
        """render_task_list emits an empty JSON array for an empty list."""
        out = _capture(lambda: self.r.render_task_list(_args(), []))
        self.assertEqual(json.loads(out), [])

    def test_task_show_is_object(self) -> None:
        """render_task_view emits a JSON object."""
        out = _capture(lambda: self.r.render_task_view(_args(), _task()))
        self.assertIsInstance(json.loads(out), dict)

    def test_task_show_slug_field(self) -> None:
        """render_task_view emits the task slug."""
        out = _capture(lambda: self.r.render_task_view(_args(), _task()))
        self.assertEqual(json.loads(out)["slug"], "fix-login-bug")

    def test_task_show_path_field_present(self) -> None:
        """render_task_view emits a path field."""
        out = _capture(lambda: self.r.render_task_view(_args(), _task()))
        self.assertIn("path", json.loads(out))

    def test_task_show_includes_timestamps(self) -> None:
        """render_task_view includes created_at and updated_at."""
        out = _capture(lambda: self.r.render_task_view(_args(), _task()))
        obj = json.loads(out)
        self.assertEqual(obj["created_at"], _CREATED_AT.isoformat())
        self.assertEqual(obj["updated_at"], _UPDATED_AT.isoformat())

    def test_task_show_includes_body(self) -> None:
        """render_task_view includes the task body."""
        out = _capture(lambda: self.r.render_task_view(_args(), _task(body="Some notes.")))
        self.assertEqual(json.loads(out)["body"], "Some notes.")

    def test_task_create_slug_field(self) -> None:
        """render_task_create emits the task slug."""
        out = _capture(lambda: self.r.render_task_create(_args(), _task()))
        self.assertEqual(json.loads(out)["slug"], "fix-login-bug")

    def test_task_create_includes_timestamps(self) -> None:
        """render_task_create includes timestamps in output."""
        out = _capture(lambda: self.r.render_task_create(_args(), _task()))
        obj = json.loads(out)
        self.assertIn("created_at", obj)
        self.assertIn("updated_at", obj)

    def test_task_edit_slug_field(self) -> None:
        """render_task_edit emits the task slug."""
        out = _capture(lambda: self.r.render_task_edit(_args(), _task()))
        self.assertEqual(json.loads(out)["slug"], "fix-login-bug")

    def test_task_assign_assigned_to_field(self) -> None:
        """render_task_assign emits the assigned_to value."""
        out = _capture(lambda: self.r.render_task_assign(_args(), _task(assigned_to="alice")))
        self.assertEqual(json.loads(out)["assigned_to"], "alice")

    def test_task_assign_slug_field(self) -> None:
        """render_task_assign emits the task slug."""
        out = _capture(lambda: self.r.render_task_assign(_args(), _task()))
        self.assertEqual(json.loads(out)["slug"], "fix-login-bug")

    def test_task_assign_includes_timestamps(self) -> None:
        """render_task_assign includes created_at and updated_at."""
        out = _capture(lambda: self.r.render_task_assign(_args(), _task()))
        obj = json.loads(out)
        self.assertIn("created_at", obj)
        self.assertIn("updated_at", obj)

    def test_task_rename_is_object(self) -> None:
        """render_task_rename emits a JSON object."""
        out = _capture(lambda: self.r.render_task_rename(_args(), _task()))
        self.assertIsInstance(json.loads(out), dict)

    def test_task_rename_slug_field(self) -> None:
        """render_task_rename emits the renamed task's new slug."""
        out = _capture(lambda: self.r.render_task_rename(_args(), _task(slug="fixed-parser")))
        self.assertEqual(json.loads(out)["slug"], "fixed-parser")

    def test_task_rename_title_field(self) -> None:
        """render_task_rename emits the renamed task's new title."""
        out = _capture(lambda: self.r.render_task_rename(_args(), _task(title="Fixed Parser")))
        self.assertEqual(json.loads(out)["title"], "Fixed Parser")

    def test_task_rename_includes_timestamps(self) -> None:
        """render_task_rename includes created_at and updated_at."""
        out = _capture(lambda: self.r.render_task_rename(_args(), _task()))
        obj = json.loads(out)
        self.assertEqual(obj["created_at"], _CREATED_AT.isoformat())
        self.assertEqual(obj["updated_at"], _UPDATED_AT.isoformat())

    def test_task_move_slug_field(self) -> None:
        """render_task_move emits the moved task's slug."""
        out = _capture(lambda: self.r.render_task_move(_args(), _task()))
        self.assertEqual(json.loads(out)["slug"], "fix-login-bug")

    def test_task_move_column_field(self) -> None:
        """render_task_move emits the task's new column as a nested ref dict."""
        out = _capture(lambda: self.r.render_task_move(_args(), _task(column="done")))
        self.assertEqual(json.loads(out)["column"]["slug"], "done")

    def test_task_move_includes_timestamps(self) -> None:
        """render_task_move includes created_at and updated_at."""
        out = _capture(lambda: self.r.render_task_move(_args(), _task()))
        obj = json.loads(out)
        self.assertEqual(obj["created_at"], _CREATED_AT.isoformat())
        self.assertEqual(obj["updated_at"], _UPDATED_AT.isoformat())

    def test_task_reorder_is_object(self) -> None:
        """render_task_reorder emits a JSON object."""
        out = _capture(lambda: self.r.render_task_reorder(_args(), (_task(), "up")))
        self.assertIsInstance(json.loads(out), dict)

    def test_task_reorder_slug_field(self) -> None:
        """render_task_reorder emits the task's slug."""
        out = _capture(lambda: self.r.render_task_reorder(_args(), (_task(), "top")))
        self.assertEqual(json.loads(out)["slug"], "fix-login-bug")

    def test_task_reorder_column_field(self) -> None:
        """render_task_reorder emits the task's column as a nested ref dict (unchanged by reorder)."""
        out = _capture(lambda: self.r.render_task_reorder(_args(), (_task(column="todo"), "down")))
        self.assertEqual(json.loads(out)["column"]["slug"], "todo")

    def test_task_reorder_includes_timestamps(self) -> None:
        """render_task_reorder includes created_at and updated_at."""
        out = _capture(lambda: self.r.render_task_reorder(_args(), (_task(), "bottom")))
        obj = json.loads(out)
        self.assertEqual(obj["created_at"], _CREATED_AT.isoformat())
        self.assertEqual(obj["updated_at"], _UPDATED_AT.isoformat())

    def test_task_delete_emits_the_task(self) -> None:
        """render_task_delete emits the deleted task's own representation."""
        out = _capture(lambda: self.r.render_task_delete(_args(path="main/todo/fix-login-bug"), _task()))
        obj = json.loads(out)
        self.assertEqual(obj["title"], "Fix login bug")
        self.assertEqual(obj["path"], "/main/todo/fix-login-bug")

    def test_task_delete_deleted_field(self) -> None:
        """render_task_delete carries the task's deleted flag."""
        out = _capture(lambda: self.r.render_task_delete(_args(path="main/todo/fix-login-bug"), _task(deleted=True)))
        self.assertTrue(json.loads(out)["deleted"])

    def test_task_list_deleted_field_is_false(self) -> None:
        """A task that was not deleted reports deleted as false."""
        out = _capture(lambda: self.r.render_task_list(_args(), [_task()]))
        self.assertFalse(json.loads(out)[0]["deleted"])


class TestJsonRendererSearch(unittest.TestCase):
    """JSON output for the search render method."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())

    def test_search_is_array(self) -> None:
        """render_search emits a JSON array."""
        out = _capture(lambda: self.r.render_search(_args(), [_task()]))
        self.assertIsInstance(json.loads(out), list)

    def test_search_slug_field(self) -> None:
        """Each search result contains the task slug."""
        out = _capture(lambda: self.r.render_search(_args(), [_task()]))
        self.assertEqual(json.loads(out)[0]["slug"], "fix-login-bug")

    def test_search_excludes_timestamps(self) -> None:
        """Search results use the minimal task representation (no timestamps or body)."""
        out = _capture(lambda: self.r.render_search(_args(), [_task()]))
        entry = json.loads(out)[0]
        for field in ("created_at", "updated_at", "body"):
            self.assertNotIn(field, entry)


class TestJsonRendererLog(unittest.TestCase):
    """JSON output for the log render method."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())

    def test_log_is_array(self) -> None:
        """render_log emits a JSON array."""
        commits = [Commit(sha="abc123"), Commit(sha="def456")]
        out = _capture(lambda: self.r.render_log(_args(), commits))
        self.assertIsInstance(json.loads(out), list)

    def test_log_sha_field(self) -> None:
        """Each log entry contains the commit SHA."""
        commits = [Commit(sha="abc123")]
        out = _capture(lambda: self.r.render_log(_args(), commits))
        self.assertEqual(json.loads(out)[0]["sha"], "abc123")

    def test_log_empty_array(self) -> None:
        """render_log emits an empty JSON array for no commits."""
        out = _capture(lambda: self.r.render_log(_args(), []))
        self.assertEqual(json.loads(out), [])


class TestJsonRendererStatus(unittest.TestCase):
    """JSON output for the status render method."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())
        self.status = KanbanStatus(
            user_context=UserContext(board="main"),
            board_count=2,
            column_count=8,
            task_count=15,
            index_fresh=True,
            uncommitted_changes=False,
        )

    def test_status_is_object(self) -> None:
        """render_status emits a JSON object."""
        out = _capture(lambda: self.r.render_status(_args(), self.status))
        self.assertIsInstance(json.loads(out), dict)

    def test_status_board_field(self) -> None:
        """render_status includes the active board from user context."""
        out = _capture(lambda: self.r.render_status(_args(), self.status))
        self.assertEqual(json.loads(out)["board"], "main")

    def test_status_excludes_column_field(self) -> None:
        """render_status omits column because UserContext no longer stores it."""
        out = _capture(lambda: self.r.render_status(_args(), self.status))
        self.assertNotIn("column", json.loads(out))

    def test_status_counts(self) -> None:
        """render_status includes board_count, column_count, and task_count."""
        out = _capture(lambda: self.r.render_status(_args(), self.status))
        obj = json.loads(out)
        self.assertEqual(obj["board_count"], 2)
        self.assertEqual(obj["column_count"], 8)
        self.assertEqual(obj["task_count"], 15)

    def test_status_flags(self) -> None:
        """render_status includes index_fresh and uncommitted_changes flags."""
        out = _capture(lambda: self.r.render_status(_args(), self.status))
        obj = json.loads(out)
        self.assertIs(obj["index_fresh"], True)
        self.assertIs(obj["uncommitted_changes"], False)


class TestJsonRendererConfig(unittest.TestCase):
    """JSON output for config render methods."""

    def setUp(self) -> None:
        self.r = JsonRenderer(render_service=_mock_render_service())

    def test_get_config_key_field(self) -> None:
        """render_get_config emits the key."""
        out = _capture(lambda: self.r.render_get_config(_args(key="name"), "alice"))
        self.assertEqual(json.loads(out)["key"], "name")

    def test_get_config_value_field(self) -> None:
        """render_get_config emits the value."""
        out = _capture(lambda: self.r.render_get_config(_args(key="name"), "alice"))
        self.assertEqual(json.loads(out)["value"], "alice")

    def test_set_config_key_field(self) -> None:
        """render_set_config emits the key."""
        out = _capture(lambda: self.r.render_set_config(_args(key="name", value="bob"), None))
        self.assertEqual(json.loads(out)["key"], "name")

    def test_set_config_value_field(self) -> None:
        """render_set_config emits the value."""
        out = _capture(lambda: self.r.render_set_config(_args(key="name", value="bob"), None))
        self.assertEqual(json.loads(out)["value"], "bob")

    def test_list_config_emits_every_key(self) -> None:
        """render_list_config emits the key/value mapping as an object."""
        out = _capture(lambda: self.r.render_list_config(_args(), {"user.name": "alice"}))
        self.assertEqual(json.loads(out), {"user.name": "alice"})

    def test_list_config_emits_unset_values_as_null(self) -> None:
        """An unset key is emitted as null rather than omitted."""
        out = _capture(lambda: self.r.render_list_config(_args(), {"user.name": None}))
        self.assertIsNone(json.loads(out)["user.name"])


if __name__ == "__main__":
    unittest.main()
