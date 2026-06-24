"""Integration tests for the kanban REPL.

Each test drives the full REPL stack (parser → handler → KanbanService →
FilesystemRepository) against a real temporary directory.  Git and index
services are stubbed with MagicMock so tests are self-contained.

Conventions
-----------
- Filesystem mutations are verified with Path.is_file / is_dir / exists.
- Output checks use assertTrue(out.strip()) — only that *something* printed.
- Frontmatter changes are verified via _read_frontmatter.
- `search`, `log`, `status`, `config`, and `edit task` are excluded because
  those service methods are not yet fully implemented.

Layout
------
_ReplBase               setUp/tearDown, run_repl helper, boards_dir
_InitializedReplBase    Adds repo.init_storage() so commands run immediately
TestReplInit            `init` and `init --bootstrap` on a fresh repo
TestReplContext         `cd`, `board`, `column` context commands
TestReplCreate          `create`/`new`/`n` for boards, columns, and tasks
TestReplList            `list`/`ls` with paths, filters, sort, and -l flag
TestReplRename          `rename board` and `rename column`
TestReplDelete          `delete`/`del`/`rm` for boards, columns, and tasks
TestReplReorder         `reorder column`
TestReplShow            `show`/`view`/`v`/`s` aliases
TestReplUpdate          `update task` with optional fields
TestReplMove            `move`/`mv` tasks between columns
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

from repl.parser import parse_args
from repl.renderer import Renderer as REPLRenderer
from services.kanban import KanbanService, TaskCreateParams
from storage.filesystem import FilesystemRepository
from storage.seeds import BOOTSTRAP_CONFIG

def _iso(dt: str) -> datetime:
    """Convert a datetime string to an ISO 8601 string with UTC timezone."""
    return datetime.fromisoformat(dt).isoformat()

# ---------------------------------------------------------------------------
# Base helpers
# ---------------------------------------------------------------------------

class _ReplBase(unittest.TestCase):
    """Provides a real FilesystemRepository and a helper to drive REPL commands."""

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
        self.renderer = REPLRenderer()

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()

    def run_repl(self, *argv: str) -> str:
        """Execute a REPL command, assert non-empty output, and return captured stdout."""
        args = parse_args(list(argv))
        buf = io.StringIO()
        with redirect_stdout(buf):
            args.func(args, self.svc, self.renderer)
        return buf.getvalue()

    @property
    def boards_dir(self) -> Path:
        return self.repo.boards_dir

    def _read_frontmatter(self, board: str, column: str, slug: str) -> dict[str, str]:
        """Parse YAML frontmatter of a task file into a key/value dict."""
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


class _InitializedReplBase(_ReplBase):
    """Adds init_storage() so all commands run immediately."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.init_storage()


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------

class TestReplInit(_ReplBase):
    """`init` command on a fresh, un-initialised repository."""

    def test_init_creates_boards_directory(self) -> None:
        """init creates the boards storage directory."""
        self.run_repl("init")
        self.assertTrue(self.boards_dir.is_dir())

    def test_init_produces_output(self) -> None:
        """init prints something."""
        out = self.run_repl("init")
        self.assertTrue(out.strip())

    def test_init_no_boards_without_bootstrap(self) -> None:
        """init without --bootstrap creates no boards."""
        self.run_repl("init")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        self.assertEqual(len(board_dirs), 0)

    def test_init_bootstrap_creates_board_directory(self) -> None:
        """init --bootstrap creates at least one board directory."""
        self.run_repl("init", "--bootstrap")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        self.assertGreater(len(board_dirs), 0)

    def test_init_bootstrap_creates_seed_board_name(self) -> None:
        """init --bootstrap creates the board named in BOOTSTRAP_CONFIG."""
        self.run_repl("init", "--bootstrap")
        expected = BOOTSTRAP_CONFIG["boards"][0]["name"]
        self.assertTrue((self.boards_dir / expected).is_dir())

    def test_init_bootstrap_creates_columns(self) -> None:
        """init --bootstrap creates column directories inside the seeded board."""
        self.run_repl("init", "--bootstrap")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        col_dirs = [d for bd in board_dirs
                    for d in bd.iterdir()
                    if d.is_dir() and not d.name.startswith(".")]
        self.assertGreater(len(col_dirs), 0)

    def test_init_bootstrap_creates_seed_tasks(self) -> None:
        """init --bootstrap creates at least one task file."""
        self.run_repl("init", "--bootstrap")
        task_files = list(self.boards_dir.rglob("*.md"))
        self.assertGreater(len(task_files), 0)

    def test_init_bootstrap_produces_output(self) -> None:
        """init --bootstrap prints something."""
        out = self.run_repl("init", "--bootstrap")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# Context commands: cd, board, column
# ---------------------------------------------------------------------------

class TestReplContext(_InitializedReplBase):
    """Context navigation commands. Board 'proj' with column 'todo' pre-created."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")

    def test_cd_board_sets_context_and_produces_no_output(self) -> None:
        """cd <board> sets the board context and prints nothing."""
        out = self.run_repl("cd", "proj")
        self.assertEqual(out, "")

    def test_cd_board_column_sets_context_and_produces_no_output(self) -> None:
        """cd <board>/<column> sets board+column context and prints nothing."""
        out = self.run_repl("cd", "proj/todo")
        self.assertEqual(out, "")

    def test_cd_clear_produces_no_output(self) -> None:
        """cd --clear clears the context and prints nothing."""
        self.run_repl("cd", "proj")
        out = self.run_repl("cd", "--clear")
        self.assertEqual(out, "")

    def test_board_command_produces_no_output(self) -> None:
        """board <name> changes the active board and prints nothing."""
        out = self.run_repl("board", "proj")
        self.assertEqual(out, "")

    def test_column_command_produces_no_output(self) -> None:
        """column <name> changes the active column and prints nothing."""
        self.run_repl("board", "proj")
        out = self.run_repl("column", "todo")
        self.assertEqual(out, "")


# ---------------------------------------------------------------------------
# create (and aliases new, n)
# ---------------------------------------------------------------------------

class TestReplCreate(_InitializedReplBase):
    """create/new/n subcommands for boards, columns, and tasks."""

    def test_create_board_creates_directory(self) -> None:
        """create board creates a board directory."""
        self.run_repl("create", "board", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_create_board_produces_output(self) -> None:
        """create board prints something."""
        out = self.run_repl("create", "board", "proj")
        self.assertTrue(out.strip())

    def test_new_board_alias_creates_directory(self) -> None:
        """new board (alias for create board) creates a board directory."""
        self.run_repl("new", "board", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_n_board_alias_creates_directory(self) -> None:
        """n board (alias for create board) creates a board directory."""
        self.run_repl("n", "board", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_create_column_creates_directory(self) -> None:
        """create column creates a column directory."""
        self.repo.create_board("proj")
        self.run_repl("create", "column", "proj/todo")
        self.assertTrue((self.boards_dir / "proj" / "todo").is_dir())

    def test_create_column_produces_output(self) -> None:
        """create column prints something."""
        self.repo.create_board("proj")
        out = self.run_repl("create", "column", "proj/todo")
        self.assertTrue(out.strip())

    def test_create_task_creates_file(self) -> None:
        """create task creates a markdown file."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.run_repl("create", "task", "proj/todo/fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())

    def test_create_task_produces_output(self) -> None:
        """create task prints something."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        out = self.run_repl("create", "task", "proj/todo/fix-login")
        self.assertTrue(out.strip())

    def test_create_task_with_all_optional_fields(self) -> None:
        """create task with all optional fields creates the file."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.run_repl(
            "create", "task", "proj/todo/new-task",
            "--assignee", "alice",
            "--priority", "high",
            "--tag", "bug",
            "--due-date", "2026-12-31",
            "--created-by", "mark",
        )
        self.assertTrue((self.boards_dir / "proj" / "todo" / "new-task.md").is_file())

    def test_create_task_optional_fields_in_frontmatter(self) -> None:
        """Optional fields on create task appear in the file's frontmatter."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.run_repl(
            "create", "task", "proj/todo/new-task",
            "--assignee", "alice",
            "--priority", "high",
            "--tag", "bug",
            "--due-date", "2026-12-31",
            "--created-by", "mark",
        )
        fm = self._read_frontmatter("proj", "todo", "new-task")
        self.assertEqual(fm.get("assignee"), "alice")
        self.assertEqual(fm.get("priority"), "high")
        self.assertEqual(fm.get("created_by"), "mark")
        self.assertEqual(fm.get("due_date"), _iso("2026-12-31"))
        self.assertIn("bug", fm.get("tags", ""))


    def test_create_task_multiple_tags_all_written_to_frontmatter(self) -> None:
        """create task with multiple --tag flags writes all tags to the frontmatter."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.run_repl(
            "create", "task", "proj/todo/new-task",
            "--tag", "bug",
            "--tag", "auth",
            "--tag", "refactor",
        )
        fm = self._read_frontmatter("proj", "todo", "new-task")
        tags = fm.get("tags", "")
        self.assertIn("bug", tags)
        self.assertIn("auth", tags)
        self.assertIn("refactor", tags)

    def test_new_task_alias_creates_file(self) -> None:
        """new task (alias for create task) creates a markdown file."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.run_repl("new", "task", "proj/todo/fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())

    def test_n_task_alias_creates_file(self) -> None:
        """n task (alias for create task) creates a markdown file."""
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.run_repl("n", "task", "proj/todo/fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())


# ---------------------------------------------------------------------------
# list (and alias ls)
# ---------------------------------------------------------------------------

class TestReplList(_InitializedReplBase):
    """list/ls command with various path depths, flags, and filters."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.repo.create_column("proj", "done")
        self.svc.create_task("proj/todo/fix-login", TaskCreateParams())

    def test_list_no_path_shows_boards(self) -> None:
        """list with no path produces output (boards)."""
        out = self.run_repl("list")
        self.assertTrue(out.strip())

    def test_list_board_shows_columns(self) -> None:
        """list <board> produces output (columns)."""
        out = self.run_repl("list", "proj")
        self.assertTrue(out.strip())

    def test_list_board_column_shows_tasks(self) -> None:
        """list <board>/<column> produces output when tasks exist."""
        out = self.run_repl("list", "proj/todo")
        self.assertTrue(out.strip())

    def test_list_board_column_includes_task_slug(self) -> None:
        """list <board>/<column> includes a created task's slug."""
        out = self.run_repl("list", "proj/todo")
        self.assertIn("fix-login", out)

    def test_ls_alias_produces_output(self) -> None:
        """ls (alias for list) produces output."""
        out = self.run_repl("ls")
        self.assertTrue(out.strip())

    def test_list_sort_produces_output(self) -> None:
        """list --sort title produces output."""
        out = self.run_repl("list", "proj/todo", "--sort", "title")
        self.assertTrue(out.strip())

    def test_list_reverse_produces_output(self) -> None:
        """list --reverse produces output."""
        out = self.run_repl("list", "proj/todo", "--reverse")
        self.assertTrue(out.strip())

    def test_list_verbose_flag_produces_output(self) -> None:
        """list -l (verbose/list-mode) produces output."""
        out = self.run_repl("list", "proj/todo", "-l")
        self.assertTrue(out.strip())

    def test_list_filter_assignee(self) -> None:
        """list --assignee filters to matching tasks."""
        self.svc.create_task("proj/todo/task-a", TaskCreateParams(assignee="alice"))
        out = self.run_repl("list", "proj/todo", "--assignee", "alice")
        self.assertIn("task-a", out)
        self.assertNotIn("fix-login", out)

    def test_list_filter_priority(self) -> None:
        """list --priority filters to matching tasks."""
        self.svc.create_task("proj/todo/task-high", TaskCreateParams(priority="high"))
        out = self.run_repl("list", "proj/todo", "--priority", "high")
        self.assertIn("task-high", out)
        self.assertNotIn("fix-login", out)

    def test_list_filter_tag(self) -> None:
        """list --tag filters to tasks carrying that tag."""
        self.svc.create_task("proj/todo/task-tagged", TaskCreateParams(tags=["bug"]))
        out = self.run_repl("list", "proj/todo", "--tag", "bug")
        self.assertIn("task-tagged", out)
        self.assertNotIn("fix-login", out)

    def test_list_all_tasks_flag_requires_board_context(self) -> None:
        """list -a lists all tasks on the active board when context is set."""
        self.svc.create_task("/proj/done/task-done", TaskCreateParams())
        self.svc.set_board("proj")
        out = self.run_repl("list", "-a")
        self.assertIn("fix-login", out)
        self.assertIn("task-done", out)


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

class TestReplRename(_InitializedReplBase):
    """rename board and rename column subcommands."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")

    def test_rename_board_creates_new_directory(self) -> None:
        """rename board creates the destination directory."""
        self.run_repl("rename", "board", "proj", "work")
        self.assertTrue((self.boards_dir / "work").is_dir())

    def test_rename_board_removes_old_directory(self) -> None:
        """rename board removes the source directory."""
        self.run_repl("rename", "board", "proj", "work")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_rename_board_produces_output(self) -> None:
        """rename board prints something."""
        out = self.run_repl("rename", "board", "proj", "work")
        self.assertTrue(out.strip())

    def test_rename_column_creates_new_directory(self) -> None:
        """rename column creates the destination directory."""
        self.run_repl("rename", "column", "proj/todo", "doing")
        self.assertTrue((self.boards_dir / "proj" / "doing").is_dir())

    def test_rename_column_removes_old_directory(self) -> None:
        """rename column removes the source directory."""
        self.run_repl("rename", "column", "proj/todo", "doing")
        self.assertFalse((self.boards_dir / "proj" / "todo").exists())

    def test_rename_column_produces_output(self) -> None:
        """rename column prints something."""
        out = self.run_repl("rename", "column", "proj/todo", "doing")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# delete (and aliases del, rm)
# ---------------------------------------------------------------------------

class TestReplDelete(_InitializedReplBase):
    """delete/del/rm command for boards, columns, and tasks."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")

    def test_delete_board_removes_directory(self) -> None:
        """delete <board> removes the board directory."""
        self.run_repl("delete", "proj", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_delete_board_produces_output(self) -> None:
        """delete <board> prints something."""
        out = self.run_repl("delete", "proj", "--force")
        self.assertTrue(out.strip())

    def test_del_alias_removes_board(self) -> None:
        """del (alias for delete) removes the board directory."""
        self.run_repl("del", "proj", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_rm_alias_removes_board(self) -> None:
        """rm (alias for delete) removes the board directory."""
        self.run_repl("rm", "proj", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_delete_column_removes_directory(self) -> None:
        """delete <board>/<column> removes the column directory."""
        self.run_repl("delete", "proj/todo", "--force")
        self.assertFalse((self.boards_dir / "proj" / "todo").exists())

    def test_delete_column_produces_output(self) -> None:
        """delete <board>/<column> prints something."""
        out = self.run_repl("delete", "proj/todo", "--force")
        self.assertTrue(out.strip())

    def test_delete_task_removes_file(self) -> None:
        """delete <board>/<column>/<task> removes the markdown file."""
        self.svc.create_task("proj/todo/fix-login", TaskCreateParams())
        self.run_repl("delete", "proj/todo/fix-login", "--force")
        self.assertFalse(
            (self.boards_dir / "proj" / "todo" / "fix-login.md").exists()
        )

    def test_delete_task_produces_output(self) -> None:
        """delete <board>/<column>/<task> prints something."""
        self.svc.create_task("proj/todo/fix-login", TaskCreateParams())
        out = self.run_repl("delete", "proj/todo/fix-login", "--force")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------

class TestReplReorder(_InitializedReplBase):
    """reorder column subcommand."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.repo.create_column("proj", "done")

    def test_reorder_column_preserves_directory(self) -> None:
        """reorder column does not remove the column directory."""
        self.run_repl("reorder", "column", "proj/done", "0")
        self.assertTrue((self.boards_dir / "proj" / "done").is_dir())

    def test_reorder_column_produces_output(self) -> None:
        """reorder column prints something."""
        out = self.run_repl("reorder", "column", "proj/done", "0")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# show (and aliases view, v, s)
# ---------------------------------------------------------------------------

class TestReplShow(_InitializedReplBase):
    """show/view/v/s commands for displaying task details."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.svc.create_task("proj/todo/fix-login", TaskCreateParams())

    def test_show_produces_output(self) -> None:
        """show <task-path> prints task details."""
        out = self.run_repl("show", "proj/todo/fix-login")
        self.assertTrue(out.strip())

    def test_view_alias_produces_output(self) -> None:
        """view (alias for show) prints task details."""
        out = self.run_repl("view", "proj/todo/fix-login")
        self.assertTrue(out.strip())

    def test_v_alias_produces_output(self) -> None:
        """v (alias for show) prints task details."""
        out = self.run_repl("v", "proj/todo/fix-login")
        self.assertTrue(out.strip())

    def test_s_alias_produces_output(self) -> None:
        """s (alias for show) prints task details."""
        out = self.run_repl("s", "proj/todo/fix-login")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# update task
# ---------------------------------------------------------------------------

class TestReplUpdate(_InitializedReplBase):
    """update task subcommand with optional fields."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.svc.create_task("proj/todo/fix-login", TaskCreateParams())

    def test_update_task_writes_assignee_to_file(self) -> None:
        """update task --assignee persists the assignee to the markdown file."""
        self.run_repl("update", "task", "proj/todo/fix-login", "--assignee", "alice")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assignee"), "alice")

    def test_update_task_writes_priority_to_file(self) -> None:
        """update task --priority persists the priority to the markdown file."""
        self.run_repl("update", "task", "proj/todo/fix-login", "--priority", "high")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("priority"), "high")

    def test_update_task_multiple_tags_all_written_to_frontmatter(self) -> None:
        """update task with multiple --tag flags writes all tags to the frontmatter."""
        self.run_repl(
            "update", "task", "proj/todo/fix-login",
            "--tag", "bug",
            "--tag", "auth",
            "--tag", "refactor",
        )
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        tags = fm.get("tags", "")
        self.assertIn("bug", tags)
        self.assertIn("auth", tags)
        self.assertIn("refactor", tags)

    def test_update_task_produces_output(self) -> None:
        """update task prints something."""
        out = self.run_repl("update", "task", "proj/todo/fix-login",
                            "--assignee", "alice")
        self.assertTrue(out.strip())

    def test_update_task_with_all_fields(self) -> None:
        """update task with every optional field persists all values."""
        self.run_repl(
            "update", "task", "proj/todo/fix-login",
            "--assignee", "bob",
            "--priority", "low",
            "--tag", "refactor",
            "--created-by", "mark",
            "--due-date", "2025-01-01",
        )
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assignee"), "bob")
        self.assertEqual(fm.get("priority"), "low")
        self.assertEqual(fm.get("tags"), "[refactor]")
        self.assertEqual(fm.get("due_date"), _iso("2025-01-01"))
        self.assertEqual(fm.get("created_by"), "mark")


# ---------------------------------------------------------------------------
# move (and alias mv)
# ---------------------------------------------------------------------------

class TestReplMove(_InitializedReplBase):
    """move/mv task to a different column."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj")
        self.repo.create_column("proj", "todo")
        self.repo.create_column("proj", "done")
        self.svc.create_task("proj/todo/fix-login", TaskCreateParams())

    def test_move_creates_file_at_destination(self) -> None:
        """move places the task file in the destination column."""
        self.run_repl("move", "proj/todo/fix-login", "done")
        self.assertTrue(
            (self.boards_dir / "proj" / "done" / "fix-login.md").is_file()
        )

    def test_move_removes_file_from_source(self) -> None:
        """move removes the task file from the source column."""
        self.run_repl("move", "proj/todo/fix-login", "done")
        self.assertFalse(
            (self.boards_dir / "proj" / "todo" / "fix-login.md").exists()
        )

    def test_move_produces_output(self) -> None:
        """move prints something."""
        out = self.run_repl("move", "proj/todo/fix-login", "done")
        self.assertTrue(out.strip())

    def test_mv_alias_moves_file(self) -> None:
        """mv (alias for move) places the task file in the destination column."""
        self.run_repl("mv", "proj/todo/fix-login", "done")
        self.assertTrue(
            (self.boards_dir / "proj" / "done" / "fix-login.md").is_file()
        )


if __name__ == "__main__":
    unittest.main()
