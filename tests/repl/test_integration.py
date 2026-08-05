"""Integration tests for the kanban REPL.

Each test drives the full REPL stack (parser → handler → KanbanService →
FilesystemRepository) against a real temporary directory.  Git and index
services are stubbed with MagicMock so tests are self-contained.

Conventions
-----------
- Filesystem mutations are verified with Path.is_file / is_dir / exists.
- Output checks use assertTrue(out.strip()) — only that *something* printed.
- Frontmatter changes are verified via _read_frontmatter.
- `search`, `log`, `status`, and `config` are excluded because those service
  methods are not yet fully implemented.

Layout
------
_ReplBase               setUp/tearDown, run_repl helper, boards_dir
_InitializedReplBase    Adds repo.init_storage()/init_local_data() so commands run immediately
TestReplInit            `init` (main board, no tasks) and `init --bootstrap` on a fresh repo
TestReplContext         `board` context command
TestReplCreate          `create`/`new`/`n` for boards, columns, and tasks
TestReplList            `list`/`ls` with paths, filters, sort, and -l flag
TestReplBoards          `boards` listing all boards
TestReplColumns         `columns`/`cols` listing columns for a board
TestReplTasks           `tasks` listing tasks scoped to a board or board/column
TestReplRename          `rename` for boards, columns, and tasks
TestReplDelete          `delete`/`del`/`rm` for boards, columns, and tasks
TestReplReorder         `reorder column`
TestReplShow            `show`/`view`/`v`/`s` aliases
TestReplInfo            `info`/`i` aliases
TestReplEdit            `edit` (with mocked $EDITOR)
TestReplUpdate          `update task` with optional fields
TestReplUnset           `unset` for individual fields and tags
TestReplTag             `tag` add and `--remove`
TestReplComment         `comment` append
TestReplMove            `move`/`mv` tasks between columns
"""

from __future__ import annotations

import configparser
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from kanban.services.render_service import RenderService
from kanban.utils.field_renderer import for_fields
from kanban.repl.parser import parse_args
from kanban.repl.rich_renderer import RichRenderer as REPLRenderer
from kanban.models import Slug
from kanban.services.kanban import KanbanService, TaskCreateParams
from kanban.storage.filesystem import FilesystemRepository
from kanban.storage.seeds import ARCHIVE_COLUMN, BOOTSTRAP_CONFIG, DEFAULT_COLUMNS, MAIN_BOARD_SLUG

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
        self.renderer = REPLRenderer(render_service=RenderService(service=self.svc))

    def tearDown(self) -> None:
        os.chdir(self._prev_cwd)
        self._tmp.cleanup()

    def run_repl(self, *argv: str) -> str:
        """
        Execute a REPL command and return captured stdout.

        The renderer is wrapped the way the shell wraps it, so --path and --id
        report a field here exactly as they do at the prompt.
        """
        args = parse_args(list(argv))
        buf = io.StringIO()
        with redirect_stdout(buf):
            args.func(args, self.svc, for_fields(args, self.renderer))
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

    def _read_task_order(self, board: str, column: str) -> list[str]:
        """Read the task order directly from the column's .metadata INI file."""
        metadata = self.boards_dir / board / column / ".metadata"
        cfg = configparser.ConfigParser()
        cfg.read(metadata, encoding="utf-8")
        raw = cfg.get("tasks", "order", fallback="")
        return [f.replace(".md", "").strip() for f in raw.split("\n") if f.strip()]


class _InitializedReplBase(_ReplBase):
    """Adds init_storage() and init_local_data() so all commands run immediately."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.init_storage()
        self.repo.init_local_data()


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

    def test_init_creates_main_board_without_bootstrap(self) -> None:
        """init creates the main board even without --bootstrap."""
        self.run_repl("init")
        board_dirs = [d for d in self.boards_dir.iterdir()
                      if d.is_dir() and not d.name.startswith(".")]
        self.assertEqual([d.name for d in board_dirs], [MAIN_BOARD_SLUG])

    def test_init_creates_default_columns_without_bootstrap(self) -> None:
        """init creates the default columns and the archive in the main board."""
        self.run_repl("init")
        col_dirs = [d.name for d in sorted((self.boards_dir / MAIN_BOARD_SLUG).iterdir())
                    if d.is_dir() and not d.name.startswith(".")]
        expected = sorted([slug for _, slug in DEFAULT_COLUMNS] + [ARCHIVE_COLUMN[1]])
        self.assertEqual(col_dirs, expected)

    def test_init_no_tasks_without_bootstrap(self) -> None:
        """init without --bootstrap creates no tasks."""
        self.run_repl("init")
        self.assertEqual(list(self.boards_dir.rglob("*.md")), [])

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
# Context commands: board
# ---------------------------------------------------------------------------

class TestReplContext(_InitializedReplBase):
    """Context navigation commands. Board 'proj' with column 'todo' pre-created."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")

    def test_board_sets_context_and_produces_output(self) -> None:
        """board <board> sets the board context and prints something."""
        out = self.run_repl("board", "proj")
        self.assertNotEqual(out, "")

    def test_board_clears_any_previously_active_column(self) -> None:
        """board <board> keeps the selected board in context."""
        self.svc.set_board(Slug("proj"))
        self.run_repl("board", "proj")
        self.assertEqual(self.svc.user_context.board, "proj")


# ---------------------------------------------------------------------------
# create (and aliases new, n)
# ---------------------------------------------------------------------------

class TestReplCreate(_InitializedReplBase):
    """create/new/n subcommands for boards, columns, and tasks."""

    def test_create_board_creates_directory(self) -> None:
        """create board creates a board directory."""
        self.run_repl("create", "--board", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_create_board_produces_output(self) -> None:
        """create board prints something."""
        out = self.run_repl("create", "--board", "proj")
        self.assertTrue(out.strip())

    def test_new_board_alias_creates_directory(self) -> None:
        """new board (alias for create board) creates a board directory."""
        self.run_repl("new", "--board", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_n_board_alias_creates_directory(self) -> None:
        """n board (alias for create board) creates a board directory."""
        self.run_repl("n", "--board", "proj")
        self.assertTrue((self.boards_dir / "proj").is_dir())

    def test_create_column_creates_directory(self) -> None:
        """create column creates a column directory in the active board."""
        self.repo.create_board("proj", slug="proj")
        self.svc.set_board(Slug("proj"))
        self.run_repl("create", "-c", "todo")
        self.assertTrue((self.boards_dir / "proj" / "todo").is_dir())

    def test_create_column_produces_output(self) -> None:
        """create column prints something."""
        self.repo.create_board("proj", slug="proj")
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("create", "-c", "todo")
        self.assertTrue(out.strip())

    def test_create_column_requires_active_board(self) -> None:
        """create column with no active board raises rather than resolving nonsense."""
        self.repo.create_board("proj", slug="proj")
        with self.assertRaises(ValueError):
            self.run_repl("create", "-c", "todo")

    def test_create_task_creates_file(self) -> None:
        """create task creates a markdown file in the active board."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl("create", "todo", "fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())

    def test_create_task_requires_active_board(self) -> None:
        """create task with no active board raises rather than resolving nonsense."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        with self.assertRaises(ValueError):
            self.run_repl("create", "todo", "fix-login")

    def test_create_task_produces_output(self) -> None:
        """create task prints something."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("create", "todo", "fix-login")
        self.assertTrue(out.strip())

    def test_create_task_with_all_optional_fields(self) -> None:
        """create task with all optional fields creates the file."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl(
            "create", "todo", "new-task",
            "--assigned-to", "alice",
            "--priority", "high",
            "--tag", "bug",
            "--due-date", "2026-12-31",
            "--created-by", "mark",
        )
        self.assertTrue((self.boards_dir / "proj" / "todo" / "new-task.md").is_file())

    def test_create_task_optional_fields_in_frontmatter(self) -> None:
        """Optional fields on create task appear in the file's frontmatter."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl(
            "create", "todo", "new-task",
            "--assigned-to", "alice",
            "--priority", "high",
            "--tag", "bug",
            "--due-date", "2026-12-31",
            "--created-by", "mark",
        )
        fm = self._read_frontmatter("proj", "todo", "new-task")
        self.assertEqual(fm.get("assigned_to"), "alice")
        self.assertEqual(fm.get("priority"), "high")
        self.assertEqual(fm.get("created_by"), "mark")
        self.assertEqual(fm.get("due_date"), _iso("2026-12-31"))
        self.assertIn("bug", fm.get("tags", ""))

    def test_create_task_multiple_tags_all_written_to_frontmatter(self) -> None:
        """create task with multiple --tag flags writes all tags to the frontmatter."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl(
            "create", "todo", "new-task",
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
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl("new", "todo", "fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())

    def test_n_task_alias_creates_file(self) -> None:
        """n task (alias for create task) creates a markdown file."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl("n", "todo", "fix-login")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "fix-login.md").is_file())

    def test_create_task_description_writes_to_body(self) -> None:
        """create task --description writes the description text into the task body."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.run_repl("create", "todo", "fix-login",
                      "--description", "Investigate the login flow.")
        out = self.run_repl("view", "fix-login")
        self.assertIn("Investigate the login flow.", out)

    def test_create_task_edit_opens_editor(self) -> None:
        """create task --edit invokes the editor after creation."""
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        with patch("kanban.utils.interaction.subprocess.run") as mock_run:
            def _write(cmd, *args, **kwargs):
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    f.write("Edited via mock editor.")
                return None
            mock_run.side_effect = _write
            self.run_repl("create", "todo", "fix-login", "--edit")
        out = self.run_repl("view", "fix-login")
        self.assertIn("Edited via mock editor.", out)


# ---------------------------------------------------------------------------
# boards
# ---------------------------------------------------------------------------

class TestReplBoards(_InitializedReplBase):
    """boards command lists all boards."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_board("ops", slug="ops")

    def test_boards_produces_output(self) -> None:
        """boards produces output."""
        out = self.run_repl("boards")
        self.assertTrue(out.strip())

    def test_boards_slugs_flag_produces_output(self) -> None:
        """boards --slugs produces the compact slug-only output."""
        out = self.run_repl("boards", "--slugs")
        self.assertTrue(out.strip())
        self.assertIn("proj", out)
        self.assertIn("ops", out)


# ---------------------------------------------------------------------------
# columns / cols
# ---------------------------------------------------------------------------

class TestReplColumns(_InitializedReplBase):
    """columns/cols command lists columns for a board."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")

    def test_columns_uses_current_context_board(self) -> None:
        """columns with no board argument falls back to the active board context."""
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("columns")
        self.assertTrue(out.strip())

    def test_cols_alias_produces_output(self) -> None:
        """cols (alias for columns) produces output."""
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("cols")
        self.assertTrue(out.strip())

    def test_columns_slugs_flag_produces_output(self) -> None:
        """columns <board> --slugs produces the compact slug-only output."""
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("columns", "--slugs")
        self.assertTrue(out.strip())
        self.assertIn("todo", out)
        self.assertIn("done", out)


# ---------------------------------------------------------------------------
# tasks
# ---------------------------------------------------------------------------

class TestReplTasks(_InitializedReplBase):
    """tasks command lists tasks, optionally scoped to a column of the active board."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))
        self.svc.create_task(Slug("done"), TaskCreateParams(title="write-docs"))

    def test_tasks_scopes_to_todo_column(self) -> None:
        """tasks <column> includes only that column's tasks."""
        out = self.run_repl("tasks", "todo")
        self.assertIn("fix-login", out)
        self.assertNotIn("write-docs", out)

    def test_tasks_scopes_to_done_column(self) -> None:
        """tasks <column> includes only that column's tasks."""
        out = self.run_repl("tasks", "done")
        self.assertIn("write-docs", out)
        self.assertNotIn("fix-login", out)

    def test_tasks_with_no_path_uses_active_board_all_columns(self) -> None:
        """tasks with no path falls back to every task in the active board."""
        out = self.run_repl("tasks")
        self.assertIn("fix-login", out)
        self.assertIn("write-docs", out)

    def test_tasks_with_no_path_and_no_active_board_raises(self) -> None:
        """tasks with no path and no active board raises rather than listing nothing."""
        self.svc.working_board = None
        with self.assertRaises(ValueError):
            self.run_repl("tasks")

    def test_tasks_slugs_flag_produces_output(self) -> None:
        """tasks --slugs produces the compact slug-only output."""
        out = self.run_repl("tasks", "--slugs")
        self.assertIn("fix-login", out)
        self.assertIn("write-docs", out)


# ---------------------------------------------------------------------------
# rename
# ---------------------------------------------------------------------------

class TestReplRename(_InitializedReplBase):
    """rename board and rename column subcommands."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))

    def test_rename_board_creates_new_directory(self) -> None:
        """rename -b creates the destination directory for the active board."""
        self.run_repl("board", "proj")
        self.run_repl("rename", "-b", "work")
        self.assertTrue((self.boards_dir / "work").is_dir())

    def test_rename_board_removes_old_directory(self) -> None:
        """rename -b removes the source directory for the active board."""
        self.run_repl("board", "proj")
        self.run_repl("rename", "-b", "work")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_rename_board_produces_output(self) -> None:
        """rename -b prints something."""
        self.run_repl("board", "proj")
        out = self.run_repl("rename", "-b", "work")
        self.assertTrue(out.strip())

    def test_rename_active_board_updates_userdata_board(self) -> None:
        """Renaming the active board via REPL persists user-context.board with the new slug."""
        self.run_repl("board", "proj")
        self.run_repl("rename", "-b", "work")
        self.assertEqual(self.repo.get_userdata("user-context.board"), "work")

    def test_rename_column_creates_new_directory(self) -> None:
        """rename -c COLUMN creates the destination directory."""
        self.run_repl("rename", "-c", "todo", "doing")
        self.assertTrue((self.boards_dir / "proj" / "doing").is_dir())

    def test_rename_column_removes_old_directory(self) -> None:
        """rename -c COLUMN removes the source directory."""
        self.run_repl("rename", "-c", "todo", "doing")
        self.assertFalse((self.boards_dir / "proj" / "todo").exists())

    def test_rename_column_produces_output(self) -> None:
        """rename -c COLUMN prints something."""
        out = self.run_repl("rename", "-c", "todo", "doing")
        self.assertTrue(out.strip())

    def test_rename_task_creates_new_file(self) -> None:
        """rename <task-slug> creates a file with the new slug."""
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="alpha task"))
        self.run_repl("rename", "alpha-task", "Beta Task")
        self.assertTrue((self.boards_dir / "proj" / "todo" / "beta-task.md").is_file())

    def test_rename_task_removes_old_file(self) -> None:
        """rename <task-slug> removes the file with the old slug."""
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="alpha task"))
        self.run_repl("rename", "alpha-task", "Beta Task")
        self.assertFalse((self.boards_dir / "proj" / "todo" / "alpha-task.md").exists())

    def test_rename_task_produces_output(self) -> None:
        """rename <task-slug> prints something."""
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="alpha task"))
        out = self.run_repl("rename", "alpha-task", "Beta Task")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# delete (and aliases del, rm)
# ---------------------------------------------------------------------------

class TestReplDelete(_InitializedReplBase):
    """delete/del/rm command for active board, columns, and tasks."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")

    def test_delete_board_removes_directory(self) -> None:
        """delete -b removes the active board directory."""
        self.svc.set_board(Slug("proj"))
        self.run_repl("delete", "-b", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_delete_board_produces_output(self) -> None:
        """delete -b prints something."""
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("delete", "-b", "--force")
        self.assertTrue(out.strip())

    def test_del_alias_removes_board(self) -> None:
        """del -b (alias for delete) removes the active board directory."""
        self.svc.set_board(Slug("proj"))
        self.run_repl("del", "-b", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_rm_alias_removes_board(self) -> None:
        """rm -b (alias for delete) removes the active board directory."""
        self.svc.set_board(Slug("proj"))
        self.run_repl("rm", "-b", "--force")
        self.assertFalse((self.boards_dir / "proj").exists())

    def test_delete_board_without_active_board_raises(self) -> None:
        """delete -b raises when no board is active."""
        with self.assertRaises(ValueError):
            self.run_repl("delete", "-b", "--force")

    def test_delete_column_removes_directory(self) -> None:
        """delete <board>/<column> removes the column directory."""
        self.svc.set_board(Slug("proj"))
        self.run_repl("delete", "-c", "todo", "--force")
        self.assertFalse((self.boards_dir / "proj" / "todo").exists())

    def test_delete_column_produces_output(self) -> None:
        """delete <board>/<column> prints something."""
        self.svc.set_board(Slug("proj"))
        out = self.run_repl("delete", "-c", "todo", "--force")
        self.assertTrue(out.strip())

    def test_delete_task_removes_file(self) -> None:
        """delete <board>/<column>/<task> removes the markdown file."""
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))
        self.run_repl("delete", "fix-login", "--force")
        self.assertFalse(
            (self.boards_dir / "proj" / "todo" / "fix-login.md").exists()
        )

    def test_delete_task_produces_output(self) -> None:
        """delete <board>/<column>/<task> prints something."""
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))
        out = self.run_repl("delete", "fix-login", "--force")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------

class TestReplReorder(_InitializedReplBase):
    """reorder column subcommand."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        self.run_repl("board", "proj")

    def test_reorder_column_preserves_directory(self) -> None:
        """reorder column does not remove the column directory."""
        self.run_repl("reorder", "column", "done", "0")
        self.assertTrue((self.boards_dir / "proj" / "done").is_dir())

    def test_reorder_column_produces_output(self) -> None:
        """reorder column prints something."""
        out = self.run_repl("reorder", "column", "done", "0")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# show (and aliases view, v, s)
# ---------------------------------------------------------------------------

class TestReplShow(_InitializedReplBase):
    """show/view/v/s commands for displaying task details."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_show_produces_output(self) -> None:
        """show <task-path> prints task details."""
        out = self.run_repl("show", "fix-login")
        self.assertTrue(out.strip())

    def test_view_alias_produces_output(self) -> None:
        """view (alias for show) prints task details."""
        out = self.run_repl("view", "fix-login")
        self.assertTrue(out.strip())

    def test_v_alias_produces_output(self) -> None:
        """v (alias for show) prints task details."""
        out = self.run_repl("v", "fix-login")
        self.assertTrue(out.strip())

    def test_s_alias_produces_output(self) -> None:
        """s (alias for show) prints task details."""
        out = self.run_repl("s", "fix-login")
        self.assertTrue(out.strip())


# ---------------------------------------------------------------------------
# update task
# ---------------------------------------------------------------------------

class TestReplUpdate(_InitializedReplBase):
    """update task subcommand with optional fields."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_update_task_writes_assigned_to_to_file(self) -> None:
        """update task --assigned-to persists the assigned_to to the markdown file."""
        self.run_repl("update", "fix-login", "--assigned-to", "alice")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "alice")

    def test_update_task_writes_priority_to_file(self) -> None:
        """update task --priority persists the priority to the markdown file."""
        self.run_repl("update", "fix-login", "--priority", "high")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("priority"), "high")

    def test_update_task_multiple_tags_all_written_to_frontmatter(self) -> None:
        """update task with multiple --tag flags writes all tags to the frontmatter."""
        self.run_repl(
            "update", "fix-login",
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
        out = self.run_repl("update", "fix-login",
                            "--assigned-to", "alice")
        self.assertTrue(out.strip())

    def test_update_task_with_all_fields(self) -> None:
        """update task with every optional field persists all values."""
        self.run_repl(
            "update", "fix-login",
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

    def test_update_task_column_moves_task_to_destination_column(self) -> None:
        """update task --column updates then moves the task to the destination column."""
        self.repo.create_column("proj", "done", slug="done")
        self.run_repl("update", "fix-login",
                      "--assigned-to", "alice",
                      "--column", "done")
        self.assertTrue((self.boards_dir / "proj" / "done" / "fix-login.md").is_file())
        self.assertFalse((self.boards_dir / "proj" / "todo" / "fix-login.md").exists())
        fm = self._read_frontmatter("proj", "done", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "alice")

    def test_update_task_column_board_path_moves_task_to_other_board(self) -> None:
        """update task --column /board/column moves the task to that board's column."""
        self.repo.create_board("other", slug="other")
        self.repo.create_column("other", "todo", slug="todo")
        self.run_repl("update", "fix-login",
                      "--assigned-to", "alice",
                      "--column", "/other/todo")
        self.assertTrue((self.boards_dir / "other" / "todo" / "fix-login.md").is_file())
        self.assertFalse((self.boards_dir / "proj" / "todo" / "fix-login.md").exists())
        fm = self._read_frontmatter("other", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "alice")

    def test_update_task_description_writes_to_body(self) -> None:
        """update task --description writes the text into the task body."""
        self.run_repl("update", "fix-login",
                      "--description", "Reproduce and fix the login bug.")
        out = self.run_repl("view", "fix-login")
        self.assertIn("Reproduce and fix the login bug.", out)

    def test_update_task_tag_merges_with_existing_tags(self) -> None:
        """update task --tag merges the new tag with any existing tags."""
        self.run_repl("update", "fix-login", "--tag", "bug")
        self.run_repl("update", "fix-login", "--tag", "auth")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        tags = fm.get("tags", "")
        self.assertIn("bug", tags)
        self.assertIn("auth", tags)


# ---------------------------------------------------------------------------
# move (and alias mv)
# ---------------------------------------------------------------------------

class TestReplMove(_InitializedReplBase):
    """move/mv task to a different column."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.repo.create_column("proj", "done", slug="done")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_move_creates_file_at_destination(self) -> None:
        """move places the task file in the destination column."""
        self.run_repl("move", "fix-login", "done")
        self.assertTrue(
            (self.boards_dir / "proj" / "done" / "fix-login.md").is_file()
        )

    def test_move_removes_file_from_source(self) -> None:
        """move removes the task file from the source column."""
        self.run_repl("move", "fix-login", "done")
        self.assertFalse(
            (self.boards_dir / "proj" / "todo" / "fix-login.md").exists()
        )

    def test_move_produces_output(self) -> None:
        """move prints something."""
        out = self.run_repl("move", "fix-login", "done")
        self.assertTrue(out.strip())

    def test_mv_alias_moves_file(self) -> None:
        """mv (alias for move) places the task file in the destination column."""
        self.run_repl("mv", "fix-login", "done")
        self.assertTrue(
            (self.boards_dir / "proj" / "done" / "fix-login.md").is_file()
        )

    def test_move_to_board_path_places_file_on_other_board(self) -> None:
        """move with a /board/column destination moves the task to that board."""
        self.repo.create_board("other", slug="other")
        self.repo.create_column("other", "todo", slug="todo")
        self.run_repl("move", "fix-login", "/other/todo")
        self.assertTrue(
            (self.boards_dir / "other" / "todo" / "fix-login.md").is_file()
        )
        self.assertFalse(
            (self.boards_dir / "proj" / "todo" / "fix-login.md").exists()
        )

    def test_move_to_board_path_leaves_active_board_unchanged(self) -> None:
        """move to another board does not switch the active board."""
        self.repo.create_board("other", slug="other")
        self.repo.create_column("other", "todo", slug="todo")
        self.run_repl("move", "fix-login", "/other/todo")
        self.assertEqual(self.svc.working_board, Slug("proj"))


class TestReplMoveReorder(_InitializedReplBase):
    """move/mv reorder ops (--top, --bottom, --up, --down) within a column."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="first"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="second"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="third"))

    def test_move_top_updates_metadata_order(self) -> None:
        """move --top places the task first in the column's metadata order."""
        self.run_repl("move", "third", "--top")
        self.assertEqual(self._read_task_order("proj", "todo"), ["third", "first", "second"])

    def test_move_bottom_updates_metadata_order(self) -> None:
        """move --bottom places the task last in the column's metadata order."""
        self.run_repl("move", "first", "--bottom")
        self.assertEqual(self._read_task_order("proj", "todo"), ["second", "third", "first"])

    def test_move_up_updates_metadata_order(self) -> None:
        """move --up moves the task one position earlier in the column's metadata order."""
        self.run_repl("move", "third", "--up")
        self.assertEqual(self._read_task_order("proj", "todo"), ["first", "third", "second"])

    def test_move_down_updates_metadata_order(self) -> None:
        """move --down moves the task one position later in the column's metadata order."""
        self.run_repl("move", "first", "--down")
        self.assertEqual(self._read_task_order("proj", "todo"), ["second", "first", "third"])

    def test_move_reorder_produces_output(self) -> None:
        """move --top prints something."""
        out = self.run_repl("move", "third", "--top")
        self.assertTrue(out.strip())

    def test_mv_alias_reorder_updates_metadata_order(self) -> None:
        """mv --bottom (alias for move) places the task last in the column's metadata order."""
        self.run_repl("mv", "first", "--bottom")
        self.assertEqual(self._read_task_order("proj", "todo"), ["second", "third", "first"])


class TestReplAssign(_InitializedReplBase):
    """assign task to a user."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_assign_writes_assigned_to_frontmatter(self) -> None:
        """assign persists assigned_to to the task's frontmatter."""
        self.run_repl("assign", "fix-login", "alice")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "alice")

    def test_assign_overwrites_previous_assigned_to(self) -> None:
        """assign replaces an existing assigned_to value."""
        self.run_repl("assign", "fix-login", "alice")
        self.run_repl("assign", "fix-login", "bob")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("assigned_to"), "bob")

    def test_assign_produces_output(self) -> None:
        """assign prints the new assigned_to."""
        out = self.run_repl("assign", "fix-login", "alice")
        self.assertTrue(out.strip())
        self.assertIn("alice", out)

    def test_assign_remove_clears_assigned_to_in_frontmatter(self) -> None:
        """assign --remove clears assigned_to in the frontmatter."""
        self.run_repl("assign", "fix-login", "alice")
        self.run_repl("assign", "fix-login", "--remove")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertNotIn("assigned_to", fm)


# ---------------------------------------------------------------------------
# info (and alias i)
# ---------------------------------------------------------------------------

class TestReplInfo(_InitializedReplBase):
    """info/i commands for displaying task metadata without the body."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_info_produces_output(self) -> None:
        """info <task-slug> prints task metadata."""
        out = self.run_repl("info", "fix-login")
        self.assertTrue(out.strip())
        self.assertIn("fix-login", out)

    def test_i_alias_produces_output(self) -> None:
        """i (alias for info) prints task metadata."""
        out = self.run_repl("i", "fix-login")
        self.assertTrue(out.strip())
        self.assertIn("fix-login", out)


# ---------------------------------------------------------------------------
# edit
# ---------------------------------------------------------------------------

class TestReplEdit(_InitializedReplBase):
    """edit command opens the task body in the configured editor."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_edit_writes_body_via_editor(self) -> None:
        """edit <task-slug> persists whatever the editor writes to the task body."""
        with patch("kanban.utils.interaction.subprocess.run") as mock_run:
            def _write(cmd, *args, **kwargs):
                with open(cmd[-1], "w", encoding="utf-8") as f:
                    f.write("Investigate the login flow.")
                return None
            mock_run.side_effect = _write
            self.run_repl("edit", "fix-login")
        out = self.run_repl("view", "fix-login")
        self.assertIn("Investigate the login flow.", out)


# ---------------------------------------------------------------------------
# unset
# ---------------------------------------------------------------------------

class TestReplUnset(_InitializedReplBase):
    """unset subcommand for clearing individual task fields."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))

    def test_unset_assigned_to_removes_field_from_frontmatter(self) -> None:
        """unset --assigned-to removes assigned_to from the frontmatter."""
        self.run_repl("create", "todo", "fix-login", "--assigned-to", "alice")
        self.run_repl("unset", "fix-login", "--assigned-to")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertNotIn("assigned_to", fm)

    def test_unset_priority_removes_field_from_frontmatter(self) -> None:
        """unset --priority removes priority from the frontmatter."""
        self.run_repl("create", "todo", "fix-login", "--priority", "high")
        self.run_repl("unset", "fix-login", "--priority")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertNotIn("priority", fm)

    def test_unset_due_date_removes_field_from_frontmatter(self) -> None:
        """unset --due-date removes due_date from the frontmatter."""
        self.run_repl("create", "todo", "fix-login", "--due-date", "2026-12-31")
        self.run_repl("unset", "fix-login", "--due-date")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertNotIn("due_date", fm)

    def test_unset_created_by_removes_field_from_frontmatter(self) -> None:
        """unset --created-by removes created_by from the frontmatter."""
        self.run_repl("create", "todo", "fix-login", "--created-by", "mark")
        self.run_repl("unset", "fix-login", "--created-by")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertNotIn("created_by", fm)

    def test_unset_tag_removes_tag_from_frontmatter(self) -> None:
        """unset --tag removes the given tag from the frontmatter."""
        self.run_repl("create", "todo", "fix-login", "--tag", "bug", "--tag", "auth")
        self.run_repl("unset", "fix-login", "--tag", "bug")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        tags = fm.get("tags", "")
        self.assertNotIn("bug", tags)
        self.assertIn("auth", tags)

    def test_unset_description_removes_description_body(self) -> None:
        """unset --description clears the Description section of the body."""
        self.run_repl("create", "todo", "fix-login",
                      "--description", "Investigate the login flow.")
        self.run_repl("unset", "fix-login", "--description")
        out = self.run_repl("view", "fix-login")
        self.assertNotIn("Investigate the login flow.", out)


# ---------------------------------------------------------------------------
# tag
# ---------------------------------------------------------------------------

class TestReplTag(_InitializedReplBase):
    """tag subcommand for adding and removing tags on a task."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_tag_adds_tag_to_frontmatter(self) -> None:
        """tag <task> <tag> adds the tag to the frontmatter."""
        self.run_repl("tag", "fix-login", "bug")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertIn("bug", fm.get("tags", ""))

    def test_tag_does_not_duplicate_existing_tag(self) -> None:
        """tag on a tag that already exists is a no-op (no duplicate)."""
        self.run_repl("tag", "fix-login", "bug")
        self.run_repl("tag", "fix-login", "bug")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        self.assertEqual(fm.get("tags"), "[bug]")

    def test_tag_remove_removes_tag_from_frontmatter(self) -> None:
        """tag --remove removes the given tag from the frontmatter."""
        self.run_repl("tag", "fix-login", "bug")
        self.run_repl("tag", "fix-login", "auth")
        self.run_repl("tag", "fix-login", "bug", "--remove")
        fm = self._read_frontmatter("proj", "todo", "fix-login")
        tags = fm.get("tags", "")
        self.assertNotIn("bug", tags)
        self.assertIn("auth", tags)


# ---------------------------------------------------------------------------
# comment
# ---------------------------------------------------------------------------

class TestReplComment(_InitializedReplBase):
    """comment subcommand for appending comments to a task body."""

    def setUp(self) -> None:
        super().setUp()
        self.repo.create_board("proj", slug="proj")
        self.repo.create_column("proj", "todo", slug="todo")
        self.svc.set_board(Slug("proj"))
        self.svc.create_task(Slug("todo"), TaskCreateParams(title="fix-login"))

    def test_comment_appends_comment_to_body(self) -> None:
        """comment appends the given text to the task body."""
        self.run_repl("comment", "fix-login", "Looks like a session bug.")
        out = self.run_repl("view", "fix-login")
        self.assertIn("Looks like a session bug.", out)

    def test_comment_creates_comments_heading(self) -> None:
        """comment inserts a `# Comments` heading before the first comment."""
        self.run_repl("comment", "fix-login", "First comment.")
        out = self.run_repl("view", "fix-login")
        self.assertIn("Comments", out)


# ---------------------------------------------------------------------------
# English names (name / slug distinction)
# ---------------------------------------------------------------------------

class TestReplBoardEnglishNames(_InitializedReplBase):
    """Board commands with multi-word English display names."""

    def test_create_uses_slug_for_directory(self) -> None:
        """create board with a space-containing name creates a directory at the kebab slug."""
        self.run_repl("create", "--board", "My Project")
        self.assertTrue((self.boards_dir / "my-project").is_dir())

    def test_create_output_contains_name(self) -> None:
        """create board prints the full display name."""
        out = self.run_repl("create", "--board", "My Project")
        self.assertIn("My Project", out)

    def test_create_output_contains_slug(self) -> None:
        """create board prints the derived slug."""
        out = self.run_repl("create", "--board", "My Project")
        self.assertIn("my-project", out)

    def test_rename_uses_new_slug_for_directory(self) -> None:
        """rename -b moves the active board to the slug derived from the new display name."""
        self.run_repl("create", "--board", "My Project")
        self.run_repl("board", "my-project")
        self.run_repl("rename", "-b", "My Renamed Project")
        self.assertTrue((self.boards_dir / "my-renamed-project").is_dir())

    def test_rename_removes_old_slug_directory(self) -> None:
        """rename -b removes the old slug directory for the active board."""
        self.run_repl("create", "--board", "My Project")
        self.run_repl("board", "my-project")
        self.run_repl("rename", "-b", "My Renamed Project")
        self.assertFalse((self.boards_dir / "my-project").exists())

    def test_rename_output_contains_new_name(self) -> None:
        """rename -b prints the new display name."""
        self.run_repl("create", "--board", "My Project")
        self.run_repl("board", "my-project")
        out = self.run_repl("rename", "-b", "My Renamed Project")
        self.assertIn("My Renamed Project", out)

    def test_rename_output_contains_new_slug(self) -> None:
        """rename -b prints the new derived slug."""
        self.run_repl("create", "--board", "My Project")
        self.run_repl("board", "my-project")
        out = self.run_repl("rename", "-b", "My Renamed Project")
        self.assertIn("my-renamed-project", out)


class TestReplColumnEnglishNames(_InitializedReplBase):
    """Column commands with multi-word English display names."""

    def setUp(self) -> None:
        super().setUp()
        # Create with no default columns so later column create tests don't collide.
        self.svc.create_board("My Project", columns=[])
        self.svc.set_board(Slug("my-project"))

    def test_create_uses_slug_for_directory(self) -> None:
        """create column with a space-containing name creates a directory at the kebab slug."""
        self.run_repl("create", "-c", "On Hold")
        self.assertTrue((self.boards_dir / "my-project" / "on-hold").is_dir())

    def test_create_output_contains_name(self) -> None:
        """create column prints the full display name."""
        out = self.run_repl("create", "-c", "On Hold")
        self.assertIn("On Hold", out)

    def test_create_output_contains_slug(self) -> None:
        """create column prints the derived slug."""
        out = self.run_repl("create", "-c", "On Hold")
        self.assertIn("on-hold", out)

    def test_rename_uses_new_slug_for_directory(self) -> None:
        """rename column moves the directory to the slug derived from the new display name."""
        self.run_repl("create", "-c", "backlog")
        self.run_repl("rename", "-c", "backlog", "Work Queue")
        self.assertTrue((self.boards_dir / "my-project" / "work-queue").is_dir())

    def test_rename_removes_old_slug_directory(self) -> None:
        """rename column removes the old slug directory."""
        self.run_repl("create", "-c", "backlog")
        self.run_repl("rename", "-c", "backlog", "Work Queue")
        self.assertFalse((self.boards_dir / "my-project" / "backlog").exists())

    def test_rename_output_contains_new_name(self) -> None:
        """rename column prints the new display name."""
        self.run_repl("create", "-c", "backlog")
        out = self.run_repl("rename", "-c", "backlog", "Work Queue")
        self.assertIn("Work Queue", out)

    def test_rename_output_contains_new_slug(self) -> None:
        """rename column prints the new derived slug."""
        self.run_repl("create", "-c", "backlog")
        out = self.run_repl("rename", "-c", "backlog", "Work Queue")
        self.assertIn("work-queue", out)


class TestReplTaskEnglishNames(_InitializedReplBase):
    """Task commands with multi-word English display names."""

    def setUp(self) -> None:
        super().setUp()
        # board create adds default columns including "To Do" (slug "todo").
        self.run_repl("create", "--board", "My Project")
        self.svc.set_board(Slug("my-project"))

    def test_create_uses_slug_for_filename(self) -> None:
        """create task with a space-containing title creates a file at the kebab slug."""
        self.run_repl("create", "todo", "Fix Login Bug")
        self.assertTrue(
            (self.boards_dir / "my-project" / "todo" / "fix-login-bug.md").is_file()
        )

    def test_create_output_contains_title(self) -> None:
        """create task prints the full display title."""
        out = self.run_repl("create", "todo", "Fix Login Bug")
        self.assertIn("Fix Login Bug", out)

    def test_create_output_contains_slug(self) -> None:
        """create task prints the derived slug."""
        out = self.run_repl("create", "todo", "Fix Login Bug")
        self.assertIn("fix-login-bug", out)


class TestReplConfig(_InitializedReplBase):
    """`config` with and without a subcommand against a real .kanban/config file."""

    def test_set_then_get_round_trips(self) -> None:
        """A value written by `config set` is returned by `config get`."""
        self.run_repl("config", "set", "user.name", "philip")
        self.assertIn("philip", self.run_repl("config", "get", "user.name"))

    def test_bare_config_lists_set_value(self) -> None:
        """Bare `config` shows the key and its stored value."""
        self.run_repl("config", "set", "user.name", "philip")
        out = self.run_repl("config")
        self.assertIn("user.name", out)
        self.assertIn("philip", out)

    def test_bare_config_lists_unset_keys(self) -> None:
        """Bare `config` lists supported keys even when they have no value."""
        self.assertIn("user.name", self.run_repl("config"))


if __name__ == "__main__":
    unittest.main()
