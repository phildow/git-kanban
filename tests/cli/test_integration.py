"""Integration tests for the kanban CLI.

Each test drives the full CLI stack (parser → handler → KanbanService →
FilesystemRepository) against a real temporary directory.  Git and index
services are stubbed with MagicMock so tests are self-contained.

Conventions
-----------
- Filesystem mutations are verified by checking Path.is_file / is_dir / exists.
- Output checks use assertIn / assertTrue(out.strip()); for --verbose output the
  only assertion is that *something* was printed, not what.
- JSON output is parsed and key fields are asserted.
- `log`, `search`, `status`, `config`, and `task edit` are excluded because
  those service methods are not yet fully implemented.

Layout
------
_CLIBase            setUp/tearDown, run_cli/run_json helpers, boards_dir
_InitializedBase    Adds repo.init_storage() so commands run immediately
TestInitCommand     `init` and `init --bootstrap` on a fresh repo
TestBoardCLI        All board subcommands + format and sort flags
TestColumnCLI       All column subcommands (board "proj" pre-created)
TestTaskCLI         All task subcommands (proj/todo + proj/done pre-created)
"""

from __future__ import annotations

import configparser
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from cli.parser import parse_args
from cli.renderer import Renderer
from cli.json_renderer import JsonRenderer
from services.kanban import KanbanService
from storage.filesystem import FilesystemRepository
from storage.seeds import BOOTSTRAP_CONFIG

def _iso(dt: str) -> datetime:
    """Convert a datetime string to an ISO 8601 string with UTC timezone."""
    return datetime.fromisoformat(dt).isoformat()

# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------

class _CLIBase(unittest.TestCase):
    """Provides a real FilesystemRepository and helpers to drive CLI commands."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._prev_cwd = os.getcwd()
        os.chdir(self.root)
        self.repo = FilesystemRepository(root=self.root)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=MagicMock(),
            git_service=MagicMock(),
        )
        self.renderer = Renderer()
        self.json_renderer = JsonRenderer()

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()

    def run_cli(self, *argv: str) -> str:
        """Execute a CLI command and return captured stdout."""
        args = parse_args(list(argv))
        buf = io.StringIO()
        with redirect_stdout(buf):
            args.func(args, self.svc, self.renderer, self.json_renderer)
        return buf.getvalue()

    def run_json(self, *argv: str) -> object:
        """Execute a CLI command and return parsed JSON output."""
        return json.loads(self.run_cli(*argv))

    @property
    def boards_dir(self) -> Path:
        return self.repo.boards_dir

    def _read_frontmatter(self, board: str, column: str, slug: str) -> dict[str, str]:
        """Parse the YAML frontmatter of a task file into a key/value dict."""
        path = self.boards_dir / board / column / f"{slug}.md"
        lines = path.read_text(encoding="utf-8").splitlines()
        fm: dict[str, str] = {}
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    fm[k.strip()] = v.strip()
        return fm

    def _read_task_order(self, board: str, column: str) -> list[str]:
        """Read the task order directly from the column's .metadata INI file."""
        metadata = self.boards_dir / board / column / ".metadata"
        cfg = configparser.ConfigParser()
        cfg.read(metadata, encoding="utf-8")
        raw = cfg.get("tasks", "order", fallback="")
        return [f.replace(".md", "").strip() for f in raw.split("\n") if f.strip()]


class _InitializedBase(_CLIBase):
    """Adds init_storage() so all commands can run immediately."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.init_storage()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestInitCommand(_CLIBase):
    """`init` command on a fresh, un-initialised repository."""

    def test_init_creates_boards_directory(self) -> None:
        """init creates the boards storage directory."""
        self.run_cli("init")
        self.assertTrue(self.boards_dir.is_dir())

    def test_init_no_boards_created_without_bootstrap(self) -> None:
        """init without --bootstrap creates storage but no boards."""
        self.run_cli("init")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        self.assertEqual(len(board_dirs), 0)

    def test_init_bootstrap_creates_board_directory(self) -> None:
        """init --bootstrap creates at least one board directory."""
        self.run_cli("init", "--bootstrap")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        self.assertGreater(len(board_dirs), 0)

    def test_init_bootstrap_creates_columns(self) -> None:
        """init --bootstrap creates column directories inside the seeded board."""
        self.run_cli("init", "--bootstrap")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        col_dirs = [d for bd in board_dirs
                    for d in bd.iterdir()
                    if d.is_dir() and not d.name.startswith(".")]
        self.assertGreater(len(col_dirs), 0)

    def test_init_bootstrap_creates_seed_board_name(self) -> None:
        """init --bootstrap creates the board named in BOOTSTRAP_CONFIG."""
        self.run_cli("init", "--bootstrap")
        expected = BOOTSTRAP_CONFIG["boards"][0]["name"]
        self.assertTrue((self.boards_dir / expected).is_dir())

    def test_init_bootstrap_creates_seed_tasks(self) -> None:
        """init --bootstrap creates at least one task file."""
        self.run_cli("init", "--bootstrap")
        task_files = list(self.boards_dir.rglob("*.md"))
        self.assertGreater(len(task_files), 0)

    def test_init_without_verbose_produces_no_output(self) -> None:
        """init without --verbose produces no output."""
        out = self.run_cli("init")
        self.assertEqual(out, "")

    def test_init_bootstrap_without_verbose_produces_no_output(self) -> None:
        """init --bootstrap without --verbose produces no output."""
        out = self.run_cli("init", "--bootstrap")
        self.assertEqual(out, "")


# ---------------------------------------------------------------------------
# board
# ---------------------------------------------------------------------------

class TestBoardCLI(_InitializedBase):
    """All board subcommands including format and sort flags."""

    def test_board_create_creates_directory(self) -> None:
        """board create creates a board directory."""
        self.run_cli("board", "create", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_board_create_verbose_prints_output(self) -> None:
        """board create --verbose prints something."""
        out = self.run_cli("board", "create", "proj", "--verbose")
        self.assertTrue(out.strip())

    def test_board_create_without_verbose_produces_no_output(self) -> None:
        """board create without --verbose produces no output."""
        out = self.run_cli("board", "create", "proj")
        self.assertEqual(out, "")

    def test_board_list_empty(self) -> None:
        """board list with no boards reports empty state."""
        out = self.run_cli("board", "list")
        self.assertTrue(out.strip())

    def test_board_list_plain_includes_board_name(self) -> None:
        """board list (plain) includes the created board name."""
        self.repo.create_board("proj", slug="proj")
        out = self.run_cli("board", "list")
        self.assertIn("proj", out)

    def test_board_list_table_prints_output(self) -> None:
        """board list --format table produces output."""
        self.repo.create_board("proj", slug="proj")
        out = self.run_cli("board", "list", "--format", "table")
        self.assertTrue(out.strip())

    def test_board_list_json_is_array(self) -> None:
        """board list --format json emits a JSON array."""
        self.repo.create_board("proj", slug="proj")
        data = self.run_json("board", "list", "--format", "json")
        self.assertIsInstance(data, list)

    def test_board_list_json_name_field(self) -> None:
        """board list --format json includes a name field for each board."""
        self.repo.create_board("proj", slug="proj")
        data = self.run_json("board", "list", "--format", "json")
        self.assertEqual(data[0]["name"], "proj")

    def test_board_list_json_column_count_field(self) -> None:
        """board list --format json includes a column_count field."""
        self.repo.create_board("proj", slug="proj")
        data = self.run_json("board", "list", "--format", "json")
        self.assertIn("column_count", data[0])

    def test_board_list_json_empty_is_array(self) -> None:
        """board list --format json emits an empty array when there are no boards."""
        data = self.run_json("board", "list", "--format", "json")
        self.assertEqual(data, [])

    def test_board_list_sort(self) -> None:
        """board list --sort title includes all boards."""
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_board("beta", slug="beta")
        out = self.run_cli("board", "list", "--sort", "title")
        self.assertIn("alpha", out)
        self.assertIn("beta", out)

    def test_board_list_reverse(self) -> None:
        """board list --reverse includes all boards."""
        self.repo.create_board("alpha", slug="alpha")
        self.repo.create_board("beta", slug="beta")
        out = self.run_cli("board", "list", "--reverse")
        self.assertIn("alpha", out)
        self.assertIn("beta", out)

    def test_board_rename_creates_new_directory(self) -> None:
        """board rename creates the destination directory."""
        self.repo.create_board("proj", slug="proj")
        self.run_cli("board", "rename", "proj", "work")
        self.assertTrue((self.boards_dir / "work").is_dir())

    def test_board_rename_removes_old_directory(self) -> None:
        """board rename removes the source directory."""
        self.repo.create_board("proj", slug="proj")
        self.run_cli("board", "rename", "proj", "work")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_board_rename_verbose_prints_output(self) -> None:
        """board rename --verbose prints something."""
        self.repo.create_board("proj", slug="proj")
        out = self.run_cli("board", "rename", "proj", "work", "--verbose")
        self.assertTrue(out.strip())

    def test_board_rename_without_verbose_produces_no_output(self) -> None:
        """board rename without --verbose produces no output."""
        self.repo.create_board("proj", slug="proj")
        out = self.run_cli("board", "rename", "proj", "work")
        self.assertEqual(out, "")

    def test_board_delete_removes_directory(self) -> None:
        """board delete removes the board directory."""
        self.repo.create_board("proj", slug="proj")
        self.run_cli("board", "delete", "proj", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_board_delete_verbose_prints_output(self) -> None:
        """board delete --verbose prints something."""
        self.repo.create_board("proj", slug="proj")
        out = self.run_cli("board", "delete", "proj", "--force", "--verbose")
        self.assertTrue(out.strip())

    def test_board_delete_without_verbose_produces_no_output(self) -> None:
        """board delete without --verbose produces no output."""
        self.repo.create_board("proj", slug="proj")
        out = self.run_cli("board", "delete", "proj", "--force")
        self.assertEqual(out, "")


# ---------------------------------------------------------------------------
# column
# ---------------------------------------------------------------------------

class TestColumnCLI(_InitializedBase):
    """All column subcommands. Board 'proj' is pre-created."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")

    def test_column_create_creates_directory(self) -> None:
        """column create creates a column directory."""
        self.run_cli("column", "create", "proj/todo")
        self.assertTrue((self.boards_dir / "proj" / "todo").is_dir())

    def test_column_create_verbose_prints_output(self) -> None:
        """column create --verbose prints something."""
        out = self.run_cli("column", "create", "proj/todo", "--verbose")
        self.assertTrue(out.strip())

    def test_column_create_without_verbose_produces_no_output(self) -> None:
        """column create without --verbose produces no output."""
        out = self.run_cli("column", "create", "proj/todo")
        self.assertEqual(out, "")

    def test_column_list_empty(self) -> None:
        """column list with no columns reports empty state."""
        out = self.run_cli("column", "list", "proj")
        self.assertTrue(out.strip())

    def test_column_list_plain_includes_column_name(self) -> None:
        """column list (plain) includes the column name."""
        self.repo.create_column("proj", "todo", slug="todo")
        out = self.run_cli("column", "list", "proj")
        self.assertIn("todo", out)

    def test_column_list_table_prints_output(self) -> None:
        """column list --format table produces output."""
        self.repo.create_column("proj", "todo", slug="todo")
        out = self.run_cli("column", "list", "proj", "--format", "table")
        self.assertTrue(out.strip())

    def test_column_list_json_is_array(self) -> None:
        """column list --format json emits a JSON array."""
        self.repo.create_column("proj", "todo", slug="todo")
        data = self.run_json("column", "list", "proj", "--format", "json")
        self.assertIsInstance(data, list)

    def test_column_list_json_name_field(self) -> None:
        """column list --format json includes the column name."""
        self.repo.create_column("proj", "todo", slug="todo")
        data = self.run_json("column", "list", "proj", "--format", "json")
        self.assertEqual(data[0]["name"], "todo")

    def test_column_list_json_board_field(self) -> None:
        """column list --format json includes the owning board."""
        self.repo.create_column("proj", "todo", slug="todo")
        data = self.run_json("column", "list", "proj", "--format", "json")
        self.assertEqual(data[0]["board"], "proj")

    def test_column_list_json_position_field(self) -> None:
        """column list --format json includes the position field."""
        self.repo.create_column("proj", "todo", slug="todo")
        data = self.run_json("column", "list", "proj", "--format", "json")
        self.assertIn("position", data[0])

    def test_column_list_sort(self) -> None:
        """column list --sort title includes all columns."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        out = self.run_cli("column", "list", "proj", "--sort", "title")
        self.assertIn("todo", out)
        self.assertIn("done", out)

    def test_column_rename_creates_new_directory(self) -> None:
        """column rename creates the destination directory."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.run_cli("column", "rename", "proj/todo", "doing")
        self.assertTrue((self.boards_dir / "proj" / "doing").is_dir())

    def test_column_rename_removes_old_directory(self) -> None:
        """column rename removes the source directory."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.run_cli("column", "rename", "proj/todo", "doing")
        self.assertFalse((self.boards_dir / "proj" / "todo").exists())

    def test_column_rename_verbose_prints_output(self) -> None:
        """column rename --verbose prints something."""
        self.repo.create_column("proj", "todo", slug="todo")
        out = self.run_cli("column", "rename", "proj/todo", "doing", "--verbose")
        self.assertTrue(out.strip())

    def test_column_rename_without_verbose_produces_no_output(self) -> None:
        """column rename without --verbose produces no output."""
        self.repo.create_column("proj", "todo", slug="todo")
        out = self.run_cli("column", "rename", "proj/todo", "doing")
        self.assertEqual(out, "")

    def test_column_reorder_column_still_exists(self) -> None:
        """column reorder does not remove the column."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        self.run_cli("column", "reorder", "proj/done", "0")
        self.assertTrue((self.boards_dir / "proj" / "done").is_dir())

    def test_column_reorder_verbose_prints_output(self) -> None:
        """column reorder --verbose prints something."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        out = self.run_cli("column", "reorder", "proj/done", "0", "--verbose")
        self.assertTrue(out.strip())

    def test_column_reorder_without_verbose_produces_no_output(self) -> None:
        """column reorder without --verbose produces no output."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        out = self.run_cli("column", "reorder", "proj/done", "0")
        self.assertEqual(out, "")

    def test_column_delete_removes_directory(self) -> None:
        """column delete removes the column directory."""
        self.repo.create_column("proj", "todo", slug="todo")
        self.run_cli("column", "delete", "proj/todo", "--force")
        self.assertFalse((self.boards_dir / "proj" / "todo").exists())

    def test_column_delete_verbose_prints_output(self) -> None:
        """column delete --verbose prints something."""
        self.repo.create_column("proj", "todo", slug="todo")
        out = self.run_cli("column", "delete", "proj/todo", "--force", "--verbose")
        self.assertTrue(out.strip())

    def test_column_delete_without_verbose_produces_no_output(self) -> None:
        """column delete without --verbose produces no output."""
        self.repo.create_column("proj", "todo", slug="todo")
        out = self.run_cli("column", "delete", "proj/todo", "--force")
        self.assertEqual(out, "")


# ---------------------------------------------------------------------------
# task
# ---------------------------------------------------------------------------

class TestTaskCLI(_InitializedBase):
    """All task subcommands. Board 'proj' with columns 'todo' and 'done' are pre-created."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")

    # -- create ---------------------------------------------------------------

    def test_task_create_creates_file(self) -> None:
        """task create creates a markdown file at the expected path."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())

    def test_task_create_with_all_optional_fields(self) -> None:
        """task create with all optional flags creates the file."""
        self.run_cli(
            "task", "create", "proj/todo/new-task",
            "--assigned-to", "alice",
            "--priority", "high",
            "--tag", "bug",
            "--due-date", "2026-12-31",
            "--created-by", "mark",
        )
        self.assertTrue((self.boards_dir / "proj" / "todo" / "new-task.md").is_file())

    def test_task_create_optional_fields_in_frontmatter(self) -> None:
        """Optional fields passed to task create appear in the file's frontmatter."""
        self.run_cli(
            "task", "create", "proj/todo/new-task",
            "--assigned-to", "alice",
            "--priority", "high",
            "--due-date", "2026-12-31",
            "--created-by", "mark",
            "--tag", "bug",
        )
        fm = self._read_frontmatter("proj", "todo", "new-task")
        self.assertEqual(fm.get("assigned_to"), "alice")
        self.assertEqual(fm.get("priority"), "high")
        self.assertEqual(fm.get("due_date"), _iso("2026-12-31"))
        self.assertEqual(fm.get("created_by"), "mark")
        self.assertEqual(fm.get("tags"), "[bug]")

    def test_task_create_multiple_tags_all_written_to_frontmatter(self) -> None:
        """task create with multiple --tag flags writes all tags to the frontmatter."""
        self.run_cli(
            "task", "create", "proj/todo/new-task",
            "--tag", "bug",
            "--tag", "auth",
            "--tag", "refactor",
        )
        fm = self._read_frontmatter("proj", "todo", "new-task")
        tags = fm.get("tags", "")
        self.assertIn("bug", tags)
        self.assertIn("auth", tags)
        self.assertIn("refactor", tags)

    def test_task_create_verbose_prints_output(self) -> None:
        """task create --verbose prints something."""
        out = self.run_cli("task", "create", "proj/todo/fix-login", "--verbose")
        self.assertTrue(out.strip())

    def test_task_create_without_verbose_produces_no_output(self) -> None:
        """task create without --verbose produces no output."""
        out = self.run_cli("task", "create", "proj/todo/fix-login")
        self.assertEqual(out, "")

    # -- list -----------------------------------------------------------------

    def test_task_list_empty(self) -> None:
        """task list with no tasks reports empty state."""
        out = self.run_cli("task", "list", "proj/todo")
        self.assertTrue(out.strip())

    def test_task_list_plain_includes_slug(self) -> None:
        """task list (plain) includes the created task slug."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "list", "proj/todo")
        self.assertIn("fix-login", out)

    def test_task_list_table_prints_output(self) -> None:
        """task list --format table produces output."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "list", "proj/todo", "--format", "table")
        self.assertTrue(out.strip())

    def test_task_list_json_is_array(self) -> None:
        """task list --format json emits a JSON array."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "list", "proj/todo", "--format", "json")
        self.assertIsInstance(data, list)

    def test_task_list_json_id_field(self) -> None:
        """task list --format json includes the task UUID."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "list", "proj/todo", "--format", "json")
        self.assertIn("id", data[0])

    def test_task_list_json_slug_field(self) -> None:
        """task list --format json includes the slug."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "list", "proj/todo", "--format", "json")
        self.assertEqual(data[0]["slug"], "fix-login")

    def test_task_list_json_board_and_column_fields(self) -> None:
        """task list --format json includes board and column fields."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "list", "proj/todo", "--format", "json")
        self.assertEqual(data[0]["board"], "proj")
        self.assertEqual(data[0]["column"], "todo")

    def test_task_list_board_scope_includes_all_columns(self) -> None:
        """task list scoped to a board includes tasks from all columns."""
        self.run_cli("task", "create", "proj/todo/task-a")
        self.run_cli("task", "create", "proj/done/task-b")
        out = self.run_cli("task", "list", "proj")
        self.assertIn("task-a", out)
        self.assertIn("task-b", out)

    def test_task_list_filter_assigned_to(self) -> None:
        """task list --assigned-to filters to only matching tasks."""
        self.run_cli("task", "create", "proj/todo/task-a", "--assigned-to", "alice")
        self.run_cli("task", "create", "proj/todo/task-b")
        out = self.run_cli("task", "list", "proj/todo", "--assigned-to", "alice")
        self.assertIn("task-a", out)
        self.assertNotIn("task-b", out)

    def test_task_list_filter_priority(self) -> None:
        """task list --priority filters to only matching tasks."""
        self.run_cli("task", "create", "proj/todo/task-a", "--priority", "high")
        self.run_cli("task", "create", "proj/todo/task-b", "--priority", "low")
        out = self.run_cli("task", "list", "proj/todo", "--priority", "high")
        self.assertIn("task-a", out)
        self.assertNotIn("task-b", out)

    def test_task_list_filter_tag(self) -> None:
        """task list --tag filters to only tasks carrying that tag."""
        self.run_cli("task", "create", "proj/todo/task-a", "--tag", "bug")
        self.run_cli("task", "create", "proj/todo/task-b")
        out = self.run_cli("task", "list", "proj/todo", "--tag", "bug")
        self.assertIn("task-a", out)
        self.assertNotIn("task-b", out)

    def test_task_list_sort(self) -> None:
        """task list --sort title includes all tasks."""
        self.run_cli("task", "create", "proj/todo/alpha-task")
        self.run_cli("task", "create", "proj/todo/beta-task")
        out = self.run_cli("task", "list", "proj/todo", "--sort", "title")
        self.assertIn("alpha-task", out)
        self.assertIn("beta-task", out)

    def test_task_list_reverse(self) -> None:
        """task list --reverse includes all tasks."""
        self.run_cli("task", "create", "proj/todo/alpha-task")
        self.run_cli("task", "create", "proj/todo/beta-task")
        out = self.run_cli("task", "list", "proj/todo", "--reverse")
        self.assertIn("alpha-task", out)
        self.assertIn("beta-task", out)

    # -- show -----------------------------------------------------------------

    def test_task_show_plain_prints_output(self) -> None:
        """task show (plain) prints task details."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "show", "proj/todo/fix-login")
        self.assertTrue(out.strip())

    def test_task_show_plain_includes_slug(self) -> None:
        """task show (plain) includes the task slug."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "show", "proj/todo/fix-login")
        self.assertIn("fix-login", out)

    def test_task_show_json_is_object(self) -> None:
        """task show --format json emits a JSON object."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "show", "proj/todo/fix-login", "--format", "json")
        self.assertIsInstance(data, dict)

    def test_task_show_json_id_field(self) -> None:
        """task show --format json includes the task UUID."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "show", "proj/todo/fix-login", "--format", "json")
        self.assertIn("id", data)

    def test_task_show_json_includes_timestamps(self) -> None:
        """task show --format json includes created_at and updated_at."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "show", "proj/todo/fix-login", "--format", "json")
        self.assertIn("created_at", data)
        self.assertIn("updated_at", data)

    def test_task_show_json_includes_body(self) -> None:
        """task show --format json includes the body field."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "show", "proj/todo/fix-login", "--format", "json")
        self.assertIn("body", data)

    # -- update ---------------------------------------------------------------

    def test_task_update_writes_assigned_to_file(self) -> None:
        """task update --assigned-to persists the assigned_to to the markdown file."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "update", "proj/todo/fix-login", "--assigned-to", "alice")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "alice")

    def test_task_update_writes_priority_to_file(self) -> None:
        """task update --priority persists the priority to the markdown file."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "update", "proj/todo/fix-login", "--priority", "high")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("priority"), "high")

    def test_task_update_multiple_tags_all_written_to_frontmatter(self) -> None:
        """task update with multiple --tag flags writes all tags to the frontmatter."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli(
            "task", "update", "proj/todo/fix-login",
            "--tag", "bug",
            "--tag", "auth",
            "--tag", "refactor",
        )
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        tags = fm.get("tags", "")
        self.assertIn("bug", tags)
        self.assertIn("auth", tags)
        self.assertIn("refactor", tags)

    def test_task_update_verbose_prints_output(self) -> None:
        """task update --verbose prints something."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "update", "proj/todo/fix-login",
                           "--assigned-to", "alice", "--verbose")
        self.assertTrue(out.strip())

    def test_task_update_with_all_fields(self) -> None:
        """update task with every optional field persists all values."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli(
            "task", "update", "proj/todo/fix-login",
            "--assigned-to", "bob",
            "--priority", "low",
            "--tag", "refactor",
            "--created-by", "mark",
            "--due-date", "2025-01-01",
        )
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "bob")
        self.assertEqual(fm.get("priority"), "low")
        self.assertEqual(fm.get("tags"), "[refactor]")
        self.assertEqual(fm.get("due_date"), _iso("2025-01-01"))
        self.assertEqual(fm.get("created_by"), "mark")

    # -- move -----------------------------------------------------------------

    def test_task_move_creates_file_at_destination(self) -> None:
        """task move creates the file in the destination column."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "move", "proj/todo/fix-login", "done")
        self.assertTrue((self.boards_dir / "proj" / "done" / "fix-login.md").is_file())

    def test_task_move_removes_file_from_source(self) -> None:
        """task move removes the file from the source column."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "move", "proj/todo/fix-login", "done")
        self.assertFalse((self.boards_dir / "proj" / "todo" / "fix-login.md").exists())

    def test_task_move_verbose_prints_output(self) -> None:
        """task move --verbose prints something."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "move", "proj/todo/fix-login", "done", "--verbose")
        self.assertTrue(out.strip())

    def test_task_move_without_verbose_produces_no_output(self) -> None:
        """task move without --verbose produces no output."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "move", "proj/todo/fix-login", "done")
        self.assertEqual(out, "")

    # -- move reorder (within column) -----------------------------------------

    def test_task_move_top_updates_metadata_order(self) -> None:
        """task move --top places the task first in the column's metadata order."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        self.run_cli("task", "create", "proj/todo/third")
        self.run_cli("task", "move", "proj/todo/third", "--top")
        self.assertEqual(self._read_task_order("proj", "todo"), ["third", "first", "second"])

    def test_task_move_bottom_updates_metadata_order(self) -> None:
        """task move --bottom places the task last in the column's metadata order."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        self.run_cli("task", "create", "proj/todo/third")
        self.run_cli("task", "move", "proj/todo/first", "--bottom")
        self.assertEqual(self._read_task_order("proj", "todo"), ["second", "third", "first"])

    def test_task_move_up_updates_metadata_order(self) -> None:
        """task move --up moves the task one position earlier in the column's metadata order."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        self.run_cli("task", "create", "proj/todo/third")
        self.run_cli("task", "move", "proj/todo/third", "--up")
        self.assertEqual(self._read_task_order("proj", "todo"), ["first", "third", "second"])

    def test_task_move_down_updates_metadata_order(self) -> None:
        """task move --down moves the task one position later in the column's metadata order."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        self.run_cli("task", "create", "proj/todo/third")
        self.run_cli("task", "move", "proj/todo/first", "--down")
        self.assertEqual(self._read_task_order("proj", "todo"), ["second", "first", "third"])

    def test_task_move_reorder_verbose_prints_output(self) -> None:
        """task move --up --verbose prints something."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        out = self.run_cli("task", "move", "proj/todo/second", "--up", "--verbose")
        self.assertTrue(out.strip())

    def test_task_move_reorder_without_verbose_produces_no_output(self) -> None:
        """task move --up without --verbose produces no output."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        out = self.run_cli("task", "move", "proj/todo/second", "--up")
        self.assertEqual(out, "")

    def test_task_move_reorder_json_verbose_includes_slug(self) -> None:
        """task move --up --verbose --format json includes the reordered task's slug."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        data = self.run_json("task", "move", "proj/todo/second", "--up",
                             "--verbose", "--format", "json")
        self.assertEqual(data["slug"], "second")

    def test_task_move_reorder_json_verbose_column_unchanged(self) -> None:
        """task move --up --verbose --format json reflects the task's column (unchanged)."""
        self.run_cli("task", "create", "proj/todo/first")
        self.run_cli("task", "create", "proj/todo/second")
        data = self.run_json("task", "move", "proj/todo/second", "--up",
                             "--verbose", "--format", "json")
        self.assertEqual(data["column"], "todo")

    # -- assign ---------------------------------------------------------------

    def test_task_assign_writes_assigned_to_frontmatter(self) -> None:
        """task assign persists assigned_to to the task's frontmatter."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "assign", "proj/todo/fix-login", "alice")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "alice")

    def test_task_assign_overwrites_previous_assigned_to(self) -> None:
        """task assign replaces an existing assigned_to value."""
        self.run_cli("task", "create", "proj/todo/fix-login", "--assigned-to", "alice")
        self.run_cli("task", "assign", "proj/todo/fix-login", "bob")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "bob")

    def test_task_assign_verbose_prints_output(self) -> None:
        """task assign --verbose prints something."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "assign", "proj/todo/fix-login", "alice", "--verbose")
        self.assertTrue(out.strip())

    def test_task_assign_without_verbose_produces_no_output(self) -> None:
        """task assign without --verbose produces no output."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "assign", "proj/todo/fix-login", "alice")
        self.assertEqual(out, "")

    def test_task_assign_json_includes_assigned_to(self) -> None:
        """task assign --verbose --format json includes the assigned_to field."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "assign", "proj/todo/fix-login", "alice",
                             "--verbose", "--format", "json")
        self.assertEqual(data["assigned_to"], "alice")

    # -- rename ---------------------------------------------------------------

    def test_task_rename_creates_new_file(self) -> None:
        """task rename creates a file at the new slug path."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "rename", "proj/todo/fix-login", "Fix Login Bug")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login-bug.md").is_file())

    def test_task_rename_removes_old_file(self) -> None:
        """task rename removes the file at the old slug path."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "rename", "proj/todo/fix-login", "Fix Login Bug")
        self.assertFalse((self.boards_dir / "proj" / "todo" / "fix-login.md").exists())

    def test_task_rename_updates_title_in_frontmatter(self) -> None:
        """task rename writes the new title to the frontmatter."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "rename", "proj/todo/fix-login", "Fix Login Bug")
        fm = self._read_frontmatter("proj", "todo", "fix-login-bug")
        self.assertEqual(fm.get("title"), "Fix Login Bug")

    def test_task_rename_updates_slug_in_frontmatter(self) -> None:
        """task rename writes the new slug to the frontmatter."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "rename", "proj/todo/fix-login", "Fix Login Bug")
        fm = self._read_frontmatter("proj", "todo", "fix-login-bug")
        self.assertEqual(fm.get("slug"), "fix-login-bug")

    def test_task_rename_verbose_prints_output(self) -> None:
        """task rename --verbose prints something."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "rename", "proj/todo/fix-login", "Fix Login Bug", "--verbose")
        self.assertTrue(out.strip())

    def test_task_rename_without_verbose_produces_no_output(self) -> None:
        """task rename without --verbose produces no output."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "rename", "proj/todo/fix-login", "Fix Login Bug")
        self.assertEqual(out, "")

    def test_task_rename_json_verbose_includes_new_slug(self) -> None:
        """task rename --verbose --format json includes the new slug."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "rename", "proj/todo/fix-login", "Fix Login Bug",
                             "--verbose", "--format", "json")
        self.assertEqual(data["slug"], "fix-login-bug")

    def test_task_rename_json_verbose_includes_new_title(self) -> None:
        """task rename --verbose --format json includes the new title."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        data = self.run_json("task", "rename", "proj/todo/fix-login", "Fix Login Bug",
                             "--verbose", "--format", "json")
        self.assertEqual(data["title"], "Fix Login Bug")

    # -- delete ---------------------------------------------------------------

    def test_task_delete_removes_file(self) -> None:
        """task delete removes the markdown file."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        self.run_cli("task", "delete", "proj/todo/fix-login", "--force")
        self.assertFalse((self.boards_dir / "proj" / "todo" / "fix-login.md").exists())

    def test_task_delete_verbose_prints_output(self) -> None:
        """task delete --verbose prints something."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "delete", "proj/todo/fix-login",
                           "--force", "--verbose")
        self.assertTrue(out.strip())

    def test_task_delete_without_verbose_produces_no_output(self) -> None:
        """task delete without --verbose produces no output."""
        self.run_cli("task", "create", "proj/todo/fix-login")
        out = self.run_cli("task", "delete", "proj/todo/fix-login", "--force")
        self.assertEqual(out, "")


# ---------------------------------------------------------------------------
# English names (name / slug distinction)
# ---------------------------------------------------------------------------

class TestBoardCLIEnglishNames(_InitializedBase):
    """Board subcommands with multi-word English display names."""

    def test_create_uses_slug_for_directory(self) -> None:
        """board create with a space-containing name creates a directory at the kebab slug."""
        self.run_cli("board", "create", "My Project")
        self.assertTrue((self.boards_dir / "my-project").is_dir())

    def test_create_json_name(self) -> None:
        """board create --format json --verbose emits the full display name."""
        data = self.run_json("board", "create", "My Project", "--format", "json", "--verbose")
        self.assertEqual(data["name"], "My Project")

    def test_create_json_slug(self) -> None:
        """board create --format json --verbose emits the kebab-case slug."""
        data = self.run_json("board", "create", "My Project", "--format", "json", "--verbose")
        self.assertEqual(data["slug"], "my-project")

    def test_rename_uses_new_slug_for_directory(self) -> None:
        """board rename moves the directory to the slug derived from the new display name."""
        self.run_cli("board", "create", "My Project")
        self.run_cli("board", "rename", "my-project", "My Renamed Project")
        self.assertTrue((self.boards_dir / "my-renamed-project").is_dir())

    def test_rename_removes_old_slug_directory(self) -> None:
        """board rename removes the old slug directory."""
        self.run_cli("board", "create", "My Project")
        self.run_cli("board", "rename", "my-project", "My Renamed Project")
        self.assertFalse((self.boards_dir / "my-project").exists())

    def test_rename_json_name(self) -> None:
        """board rename --format json --verbose emits the new full display name."""
        self.run_cli("board", "create", "My Project")
        data = self.run_json("board", "rename", "my-project", "My Renamed Project",
                             "--format", "json", "--verbose")
        self.assertEqual(data["name"], "My Renamed Project")

    def test_rename_json_slug(self) -> None:
        """board rename --format json --verbose emits the new kebab-case slug."""
        self.run_cli("board", "create", "My Project")
        data = self.run_json("board", "rename", "my-project", "My Renamed Project",
                             "--format", "json", "--verbose")
        self.assertEqual(data["slug"], "my-renamed-project")


class TestColumnCLIEnglishNames(_InitializedBase):
    """Column subcommands with multi-word English display names."""

    def setUp(self) -> None:
        super().setUp()
        # Create with no default columns so later column create tests don't collide.
        self.svc.create_board("My Project", columns=[])

    def test_create_uses_slug_for_directory(self) -> None:
        """column create with a space-containing name creates a directory at the kebab slug."""
        self.run_cli("column", "create", "my-project/On Hold")
        self.assertTrue((self.boards_dir / "my-project" / "on-hold").is_dir())

    def test_create_json_name(self) -> None:
        """column create --format json --verbose emits the full display name."""
        data = self.run_json("column", "create", "my-project/On Hold",
                             "--format", "json", "--verbose")
        self.assertEqual(data["name"], "On Hold")

    def test_create_json_slug(self) -> None:
        """column create --format json --verbose emits the kebab-case slug."""
        data = self.run_json("column", "create", "my-project/On Hold",
                             "--format", "json", "--verbose")
        self.assertEqual(data["slug"], "on-hold")

    def test_rename_uses_new_slug_for_directory(self) -> None:
        """column rename moves the directory to the slug derived from the new display name."""
        self.run_cli("column", "create", "my-project/backlog")
        self.run_cli("column", "rename", "my-project/backlog", "Work Queue")
        self.assertTrue((self.boards_dir / "my-project" / "work-queue").is_dir())

    def test_rename_removes_old_slug_directory(self) -> None:
        """column rename removes the old slug directory."""
        self.run_cli("column", "create", "my-project/backlog")
        self.run_cli("column", "rename", "my-project/backlog", "Work Queue")
        self.assertFalse((self.boards_dir / "my-project" / "backlog").exists())

    def test_rename_json_name(self) -> None:
        """column rename --format json --verbose emits the new full display name."""
        self.run_cli("column", "create", "my-project/backlog")
        data = self.run_json("column", "rename", "my-project/backlog", "Work Queue",
                             "--format", "json", "--verbose")
        self.assertEqual(data["name"], "Work Queue")

    def test_rename_json_slug(self) -> None:
        """column rename --format json --verbose emits the new kebab-case slug."""
        self.run_cli("column", "create", "my-project/backlog")
        data = self.run_json("column", "rename", "my-project/backlog", "Work Queue",
                             "--format", "json", "--verbose")
        self.assertEqual(data["slug"], "work-queue")


class TestTaskCLIEnglishNames(_InitializedBase):
    """Task subcommands with multi-word English display names."""

    def setUp(self) -> None:
        super().setUp()
        # board create adds default columns including "To Do" (slug "todo").
        self.run_cli("board", "create", "My Project")

    def test_create_uses_slug_for_filename(self) -> None:
        """task create with a space-containing title creates a file at the kebab slug."""
        self.run_cli("task", "create", "my-project/todo/Fix Login Bug")
        self.assertTrue(
            (self.boards_dir / "my-project" / "todo" / "fix-login-bug.md").is_file()
        )

    def test_create_json_title(self) -> None:
        """task create --format json --verbose emits the full display title."""
        data = self.run_json("task", "create", "my-project/todo/Fix Login Bug",
                             "--format", "json", "--verbose")
        self.assertEqual(data["title"], "Fix Login Bug")

    def test_create_json_slug(self) -> None:
        """task create --format json --verbose emits the kebab-case slug."""
        data = self.run_json("task", "create", "my-project/todo/Fix Login Bug",
                             "--format", "json", "--verbose")
        self.assertEqual(data["slug"], "fix-login-bug")


if __name__ == "__main__":
    unittest.main()
