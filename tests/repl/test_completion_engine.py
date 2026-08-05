"""Tests for CompletionEngine, walking a fixture argparse tree.

The fixture parser mirrors the dest-naming conventions and nested
subcommand shape of the real ``repl.parser`` module (path/board/column
dests, nested "subject" subparsers, aliases, and choice-restricted
flags) without depending on its command-handler imports, so these
tests stay hermetic. The one thing taken from the real module is
``TASK_DESTINATION_METAVAR``, which the engine reads to tell a move
destination from a plain column argument; sharing the constant is what
keeps the two from drifting apart.

The fake service models the same example layout used throughout the
design discussion:

    my-project/  todo, in-progress, in-review, done
        todo:        fix-login-bug, write-api-docs, add-rate-limiting
    ops/         backlog, todo, in-progress, done
        in-progress: deploy-staging, update-certs, rotate-keys
"""

from __future__ import annotations

import argparse
import unittest
from dataclasses import dataclass
from pathlib import Path

from kanban.models import TaskFilter
from kanban.repl.completion_engine import CompletionEngine
from kanban.repl.parser import TASK_DESTINATION_METAVAR
from kanban.services.kanban import CONFIG_KEYS

_NOOP = lambda args: None  # noqa: E731 - trivial stand-in for real handlers


def _build_fixture_parser() -> argparse.ArgumentParser:
    """Build a parser exercising every completion-relevant convention."""

    parser = argparse.ArgumentParser(add_help=False, prog="")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # board: single existing-board name
    p = subparsers.add_parser("board")
    p.add_argument("board")
    p.set_defaults(func=_NOOP)

    # column: single existing-column name (within active board context)
    p = subparsers.add_parser("column")
    p.add_argument("column")
    p.set_defaults(func=_NOOP)

    # create <board|column|task> - nested subject subparser
    create_parser = subparsers.add_parser("create", aliases=["new", "n"])
    create_sub = create_parser.add_subparsers(dest="create_subject", metavar="SUBJECT")
    create_sub.required = True

    p = create_sub.add_parser("board")
    p.add_argument("board")  # new board name
    p.set_defaults(func=_NOOP)

    p = create_sub.add_parser("column")
    p.add_argument("path")  # BOARD/COLUMN, column part is new
    p.set_defaults(func=_NOOP)

    p = create_sub.add_parser("task")
    p.add_argument("path")  # BOARD/COLUMN/TITLE
    p.add_argument("-p", "--priority", choices=["low", "medium", "high"])
    p.add_argument("-w", "--assigned-to", dest="assigned_to")
    p.add_argument("-t", "--tag", action="append", dest="tags")
    p.add_argument("--created-by", dest="created_by")
    p.set_defaults(func=_NOOP)

    # rename <board|column>
    rename_parser = subparsers.add_parser("rename")
    rename_sub = rename_parser.add_subparsers(dest="rename_subject", metavar="SUBJECT")
    rename_sub.required = True

    p = rename_sub.add_parser("board")
    p.add_argument("board")  # existing board
    p.add_argument("new_name")
    p.set_defaults(func=_NOOP)

    # list: optional path
    p = subparsers.add_parser("list", aliases=["ls"])
    p.add_argument("path", nargs="?")
    p.set_defaults(func=_NOOP)

    # show: existing task path (segment-walked, no TASK metavar)
    p = subparsers.add_parser("show", aliases=["view", "s"])
    p.add_argument("path")
    p.set_defaults(func=_NOOP)

    # edit: task addressed by bare slug (metavar TASK triggers slug completion)
    p = subparsers.add_parser("edit")
    p.add_argument("path", metavar="TASK")
    p.set_defaults(func=_NOOP)

    # move: task path + a destination (a column, or a /board/column path per
    # the destination metavar)
    p = subparsers.add_parser("move", aliases=["mv"])
    p.add_argument("path")
    p.add_argument("column", metavar=TASK_DESTINATION_METAVAR)
    p.set_defaults(func=_NOOP)

    # update: task by bare slug + the same destination on a flag
    p = subparsers.add_parser("update")
    p.add_argument("path", metavar="TASK")
    p.add_argument("-c", "--column", dest="column", metavar=TASK_DESTINATION_METAVAR)
    p.set_defaults(func=_NOOP)

    # delete: a column of the active board alone, with no destination metavar
    p = subparsers.add_parser("delete")
    p.add_argument("-c", "--column", dest="column", metavar="COLUMN")
    p.set_defaults(func=_NOOP)

    # tag: positional whose dest is "tags" and metavar is "TAG"
    p = subparsers.add_parser("tag")
    p.add_argument("path")
    p.add_argument("tags", metavar="TAG")
    p.set_defaults(func=_NOOP)

    # untag: positional whose dest is "tag" (not "tags") but metavar is "TAG"
    p = subparsers.add_parser("untag")
    p.add_argument("path")
    p.add_argument("tag", metavar="TAG")
    p.set_defaults(func=_NOOP)

    # search: free-text query + flags, including a board-name flag
    p = subparsers.add_parser("search")
    p.add_argument("query")
    p.add_argument("--board")
    p.add_argument("-p", "--priority", choices=["low", "medium", "high"])
    p.set_defaults(func=_NOOP)

    # status: no arguments at all
    p = subparsers.add_parser("status")
    p.set_defaults(func=_NOOP)

    # config <get|set>: positional whose dest is "key" and metavar is "KEY"
    config_parser = subparsers.add_parser("config")
    config_parser.set_defaults(func=_NOOP)
    config_sub = config_parser.add_subparsers(dest="config_command", metavar="COMMAND")
    config_sub.required = False

    p = config_sub.add_parser("get")
    p.add_argument("key", metavar="KEY")
    p.set_defaults(func=_NOOP)

    p = config_sub.add_parser("set")
    p.add_argument("key", metavar="KEY")
    p.add_argument("value", metavar="VALUE")
    p.set_defaults(func=_NOOP)

    # exit: aliases only, no arguments
    p = subparsers.add_parser("exit", aliases=["quit", ":q"])
    p.set_defaults(func=_NOOP)

    return parser


@dataclass(frozen=True)
class _Slugged:
    """Minimal stand-in for Board/Column with a `.slug` attribute."""

    slug: str


@dataclass(frozen=True)
class _Task:
    """Minimal stand-in for Task with a `.slug` attribute."""

    slug: str


@dataclass
class _Context:
    """Minimal stand-in for the REPL's user context."""

    board: str | None = None
    column: str | None = None


class FakeKanbanService:
    """In-memory CompletionDataSource fixture for tests."""

    _BOARDS = {
        "my-project": {
            "todo": ["fix-login-bug", "write-api-docs", "add-rate-limiting"],
            "in-progress": [],
            "in-review": [],
            "done": [],
        },
        "ops": {
            "backlog": [],
            "todo": ["deploy-staging", "update-certs", "rotate-keys"],
            "in-progress": ["deploy-staging", "update-certs", "rotate-keys"],
            "done": [],
        },
    }

    _TAGS = {
        "my-project": ["bug", "docs", "urgent"],
        "ops": ["infra", "urgent"],
    }

    _ASSIGNED_TOS = {
        "my-project": ["alice", "bob"],
        "ops": ["alice", "carol"],
    }

    def __init__(self) -> None:
        self._board: str | None = None
        self._column: str | None = None

    def set_context(self, board: str | None, column: str | None) -> None:
        """Mirror the REPL's user context so path_components resolves correctly."""
        self._board = board
        self._column = column

    @property
    def working_board(self) -> str | None:
        return self._board

    def get_boards(self) -> list[_Slugged]:
        return [_Slugged(slug) for slug in self._BOARDS]

    def get_columns(self, board: str) -> list[_Slugged]:
        return [_Slugged(slug) for slug in self._BOARDS[board]]

    def get_tasks(self, path: Path | None = None, filter: TaskFilter = TaskFilter()) -> list[_Task]:
        board, column, _ = self.path_components(path)
        if board is None:
            return []
        columns = self._BOARDS.get(board, {})
        if column is None:
            # Board-wide: aggregate task slugs across every column, mirroring
            # KanbanService.get_tasks when given a board-only path.
            slugs = [slug for col_slugs in columns.values() for slug in col_slugs]
        else:
            slugs = columns.get(column, [])
        return [_Task(slug) for slug in slugs]

    def get_tags(self, board: str | None = None) -> list[str]:
        if board is None:
            tags = {tag for board_tags in self._TAGS.values() for tag in board_tags}
        else:
            tags = set(self._TAGS.get(board, []))
        return sorted(tags)

    def get_assigned_tos(self, board: str | None = None) -> list[str]:
        if board is None:
            names = {name for board_names in self._ASSIGNED_TOS.values() for name in board_names}
        else:
            names = set(self._ASSIGNED_TOS.get(board, []))
        return sorted(names)

    def path_components(self, path: str | Path | None = None) -> tuple[str | None, str | None, str | None]:
        """Resolve path against the stored user context, mirroring KanbanService."""
        if isinstance(path, Path):
            path = str(path)

        raw = path or ""
        if raw.startswith("/"):
            base = Path("/")
            rest = raw.lstrip("/")
        else:
            context_parts = [p for p in [self._board, self._column] if p]
            base = Path("/").joinpath(*context_parts) if context_parts else Path("/")
            rest = raw
        segments = [s for s in rest.rstrip("/").split("/") if s]
        resolved = base.joinpath(*segments).resolve(strict=False) if segments else base
        parts = resolved.parts
        return (
            parts[1] if len(parts) > 1 else None,
            parts[2] if len(parts) > 2 else None,
            parts[3] if len(parts) > 3 else None,
        )


class EngineTestCase(unittest.TestCase):
    """Shared fixture setup for completion engine tests."""

    def setUp(self) -> None:
        self.service = FakeKanbanService()
        self.engine = CompletionEngine(self.service, _build_fixture_parser())

    def complete(self, line: str, context: _Context | None = None) -> list[str]:
        ctx = context or _Context()
        self.service.set_context(ctx.board, ctx.column)
        return self.engine.complete(line, len(line))


class NoContextPathCompletionTests(EngineTestCase):
    """Path completion (dest="path") with no active board/column."""

    def test_lists_boards_with_no_input(self) -> None:
        self.assertEqual(self.complete("show "), ["my-project/", "ops/"])

    def test_filters_boards_by_prefix(self) -> None:
        self.assertEqual(self.complete("show my-"), ["my-project/"])

    def test_lists_columns_after_board(self) -> None:
        self.assertEqual(
            self.complete("show my-project/"),
            ["done/", "in-progress/", "in-review/", "todo/"],
        )

    def test_lists_tasks_after_column(self) -> None:
        self.assertEqual(
            self.complete("show my-project/todo/"),
            ["add-rate-limiting", "fix-login-bug", "write-api-docs"],
        )

    def test_filters_tasks_by_prefix(self) -> None:
        self.assertEqual(self.complete("show my-project/todo/fix"), ["fix-login-bug"])

    def test_leading_slash_returns_no_candidates(self) -> None:
        """Leading `/` is not a valid REPL path, so completion produces nothing."""
        self.assertEqual(self.complete("show /my-"), [])


class ContextAwarePathCompletionTests(EngineTestCase):
    """Path completion skips segments already fixed by context."""

    def test_skips_board_segment(self) -> None:
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("show ", context),
            ["done/", "in-progress/", "in-review/", "todo/"],
        )

    def test_skips_board_and_column_segments(self) -> None:
        context = _Context(board="my-project", column="todo")
        self.assertEqual(
            self.complete("show ", context),
            ["add-rate-limiting", "fix-login-bug", "write-api-docs"],
        )

    def test_leading_slash_returns_no_candidates(self) -> None:
        """Leading `/` is not a valid REPL path even with a context set."""
        context = _Context(board="my-project", column="todo")
        self.assertEqual(self.complete("show /ops/", context), [])


class TaskSlugCompletionTests(EngineTestCase):
    """Path positionals with metavar TASK complete bare task slugs board-wide."""

    def test_lists_all_task_slugs_in_active_board(self) -> None:
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("edit ", context),
            ["add-rate-limiting", "fix-login-bug", "write-api-docs"],
        )

    def test_filters_task_slugs_by_prefix(self) -> None:
        context = _Context(board="my-project")
        self.assertEqual(self.complete("edit fix", context), ["fix-login-bug"])

    def test_aggregates_across_columns(self) -> None:
        context = _Context(board="ops")
        # deploy-staging appears in both todo and in-progress; slugs de-duped view
        # is not required, but every column's tasks are reachable by slug.
        self.assertEqual(
            self.complete("edit rot", context),
            ["rotate-keys"],
        )

    def test_no_active_board_completes_nothing(self) -> None:
        self.assertEqual(self.complete("edit "), [])

    def test_slash_in_token_returns_no_candidates(self) -> None:
        """Task-slug completion expects a bare slug; a `/` disqualifies the token."""
        context = _Context(board="my-project", column="todo")
        self.assertEqual(self.complete("edit /ops/", context), [])


class MoveDestCompletionTests(EngineTestCase):
    """move's second positional (column) gets column-style completion."""

    def test_completes_first_path_argument(self) -> None:
        self.assertEqual(self.complete("move "), ["my-project/", "ops/"])

    def test_completes_destination_argument_without_context(self) -> None:
        """Without board context the column argument cannot be completed."""
        line = "move /my-project/todo/fix-login-bug "
        self.assertEqual(self.complete(line), [])

    def test_destination_respects_context(self) -> None:
        context = _Context(board="my-project")
        line = "move todo/fix-login-bug "
        self.assertEqual(
            self.complete(line, context),
            ["done", "in-progress", "in-review", "todo"],
        )

    def test_destination_filters_columns_by_prefix(self) -> None:
        """A partial column completes against the active board's columns."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("move fix-login-bug in-", context),
            ["in-progress", "in-review"],
        )


class MoveDestinationBoardCompletionTests(EngineTestCase):
    """A destination beginning with `/` completes as a board, then a column."""

    def test_slash_lists_boards(self) -> None:
        """A lone slash offers every board, each ready for a column."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("move fix-login-bug /", context),
            ["my-project/", "ops/"],
        )

    def test_filters_boards_by_prefix(self) -> None:
        """A partial board name narrows the boards offered."""
        context = _Context(board="my-project")
        self.assertEqual(self.complete("move fix-login-bug /op", context), ["ops/"])

    def test_lists_columns_of_the_named_board(self) -> None:
        """Past the board's slash the columns are that board's, not the active one's."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("move fix-login-bug /ops/", context),
            ["backlog", "done", "in-progress", "todo"],
        )

    def test_filters_columns_of_the_named_board_by_prefix(self) -> None:
        """A partial column narrows the named board's columns."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("move fix-login-bug /ops/b", context),
            ["backlog"],
        )

    def test_boards_are_offered_without_an_active_board(self) -> None:
        """An absolute destination names its own board, so no context is needed."""
        self.assertEqual(self.complete("move fix-login-bug /"), ["my-project/", "ops/"])

    def test_unknown_board_offers_nothing(self) -> None:
        """A board that does not exist has no columns to offer."""
        context = _Context(board="my-project")
        self.assertEqual(self.complete("move fix-login-bug /nope/", context), [])

    def test_deeper_than_a_column_offers_nothing(self) -> None:
        """A destination is a board and a column at most."""
        context = _Context(board="my-project")
        self.assertEqual(self.complete("move fix-login-bug /ops/todo/x", context), [])

    def test_mv_alias_completes_the_same_way(self) -> None:
        """The alias reaches the same parser and so the same destination."""
        context = _Context(board="my-project")
        self.assertEqual(self.complete("mv fix-login-bug /op", context), ["ops/"])


class UpdateColumnCompletionTests(EngineTestCase):
    """`update --column` completes as a destination; other column flags do not."""

    def test_completes_columns_of_the_active_board(self) -> None:
        """Without a slash the flag names a column of the active board."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("update fix-login-bug --column in-", context),
            ["in-progress", "in-review"],
        )

    def test_short_flag_lists_boards_after_a_slash(self) -> None:
        """The short flag completes a board the same as the long one."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("update fix-login-bug -c /", context),
            ["my-project/", "ops/"],
        )

    def test_lists_columns_of_the_named_board(self) -> None:
        """Past the board's slash the flag offers that board's columns."""
        context = _Context(board="my-project")
        self.assertEqual(
            self.complete("update fix-login-bug --column /ops/", context),
            ["backlog", "done", "in-progress", "todo"],
        )

    def test_a_plain_column_flag_does_not_complete_boards(self) -> None:
        """A column argument that is not a destination stays a bare column."""
        context = _Context(board="my-project")
        self.assertEqual(self.complete("delete --column /", context), [])


class BoardAndColumnDestCompletionTests(EngineTestCase):
    """dest="board"/"column" single-segment completion (non-path commands)."""

    def test_board_command_completes_existing_boards(self) -> None:
        self.assertEqual(self.complete("board "), ["my-project", "ops"])

    def test_rename_board_completes_existing_boards(self) -> None:
        self.assertEqual(self.complete("rename board "), ["my-project", "ops"])

    def test_column_command_completes_columns_in_active_board(self) -> None:
        context = _Context(board="ops")
        self.assertEqual(
            self.complete("column ", context),
            ["backlog", "done", "in-progress", "todo"],
        )

    def test_column_command_with_no_active_board_completes_nothing(self) -> None:
        self.assertEqual(self.complete("column "), [])


class NestedSubcommandCompletionTests(EngineTestCase):
    """Completion of nested 'subject' subcommands and their aliases."""

    def test_completes_create_subjects(self) -> None:
        self.assertEqual(self.complete("create "), ["board", "column", "task"])

    def test_resolves_alias_before_descending(self) -> None:
        self.assertEqual(self.complete("new "), ["board", "column", "task"])

    def test_filters_subjects_by_prefix(self) -> None:
        self.assertEqual(self.complete("create ta"), ["task"])


class CommandNameCompletionTests(EngineTestCase):
    """Top-level command completion, including aliases from the parser."""

    def test_completes_command_prefix(self) -> None:
        self.assertEqual(self.complete("mo"), ["move"])

    def test_includes_aliases_from_parser(self) -> None:
        self.assertIn("mv", self.complete("m"))

    def test_includes_symbolic_alias(self) -> None:
        self.assertIn(":q", self.complete(""))


class FlagCompletionTests(EngineTestCase):
    """Completion of `--flag` names and choice-restricted values."""

    def test_completes_flag_name(self) -> None:
        line = "create task /my-project/todo/new-task --pri"
        self.assertEqual(self.complete(line), ["--priority"])

    def test_completes_flag_value_from_parser_choices(self) -> None:
        line = "create task /my-project/todo/new-task --priority h"
        self.assertEqual(self.complete(line), ["high"])

    def test_free_value_flag_has_no_suggestions(self) -> None:
        line = "create task /my-project/todo/new-task --created-by al"
        self.assertEqual(self.complete(line), [])

    def test_board_flag_completes_existing_boards(self) -> None:
        line = "search bug --board my-"
        self.assertEqual(self.complete(line), ["my-project"])


class TagCompletionTests(EngineTestCase):
    """dest="tags" completion, scoped to the active board context."""

    def test_completes_tags_scoped_to_active_board(self) -> None:
        context = _Context(board="my-project")
        line = "create task /my-project/todo/new-task --tag "
        self.assertEqual(self.complete(line, context), ["bug", "docs", "urgent"])

    def test_filters_tags_by_prefix(self) -> None:
        context = _Context(board="ops")
        line = "create task /ops/todo/new-task --tag u"
        self.assertEqual(self.complete(line, context), ["urgent"])

    def test_no_active_board_completes_tags_across_all_boards(self) -> None:
        line = "create task /my-project/todo/new-task --tag "
        self.assertEqual(self.complete(line), ["bug", "docs", "infra", "urgent"])

    def test_repeated_tag_flag_still_completes(self) -> None:
        context = _Context(board="my-project")
        line = "create task /my-project/todo/new-task --tag bug --tag "
        self.assertEqual(self.complete(line, context), ["bug", "docs", "urgent"])

    def test_positional_tag_completes_when_dest_is_tags(self) -> None:
        """A positional argument whose dest is "tags" (metavar TAG) offers tag completions."""
        context = _Context(board="my-project")
        line = "tag /my-project/todo/fix-parser "
        self.assertEqual(self.complete(line, context), ["bug", "docs", "urgent"])

    def test_positional_tag_completes_when_only_metavar_is_TAG(self) -> None:
        """A positional argument whose dest is "tag" (not "tags") but metavar is "TAG" still offers tag completions."""
        context = _Context(board="my-project")
        line = "untag /my-project/todo/fix-parser "
        self.assertEqual(self.complete(line, context), ["bug", "docs", "urgent"])


class AssignedToCompletionTests(EngineTestCase):
    """dest="assigned_to" completion, scoped to the active board context."""

    def test_completes_assigned_to_scoped_to_active_board(self) -> None:
        context = _Context(board="my-project")
        line = "create task /my-project/todo/new-task --assigned-to "
        self.assertEqual(self.complete(line, context), ["alice", "bob"])

    def test_filters_assigned_to_by_prefix(self) -> None:
        context = _Context(board="ops")
        line = "create task /ops/todo/new-task --assigned-to c"
        self.assertEqual(self.complete(line, context), ["carol"])

    def test_no_active_board_completes_assigned_to_across_all_boards(self) -> None:
        line = "create task /my-project/todo/new-task --assigned-to "
        self.assertEqual(self.complete(line), ["alice", "bob", "carol"])

    def test_short_flag_completes_assigned_to(self) -> None:
        context = _Context(board="my-project")
        line = "create task /my-project/todo/new-task -w "
        self.assertEqual(self.complete(line, context), ["alice", "bob"])


class ConfigKeyCompletionTests(EngineTestCase):
    """Positionals with metavar KEY complete against the supported config keys."""

    def test_lists_all_keys_with_no_input(self) -> None:
        self.assertEqual(self.complete("config get "), sorted(CONFIG_KEYS))

    def test_filters_keys_by_prefix(self) -> None:
        self.assertEqual(self.complete("config get user."), ["user.name"])

    def test_completes_key_for_set(self) -> None:
        self.assertEqual(self.complete("config set "), sorted(CONFIG_KEYS))

    def test_unknown_prefix_completes_nothing(self) -> None:
        self.assertEqual(self.complete("config get bogus"), [])

    def test_value_after_key_has_no_suggestions(self) -> None:
        self.assertEqual(self.complete("config set user.name "), [])

    def test_completes_config_subcommands(self) -> None:
        self.assertEqual(self.complete("config "), ["get", "set"])


class FreeTextCompletionTests(EngineTestCase):
    """Positionals with no special dest name get no suggestions."""

    def test_search_query_has_no_suggestions(self) -> None:
        self.assertEqual(self.complete("search "), [])

    def test_rename_new_name_has_no_suggestions(self) -> None:
        self.assertEqual(self.complete("rename board my-project "), [])


class PartialAtTests(EngineTestCase):
    """partial_at reports the fragment a candidate replaces, not the whole token."""

    def _partial(self, line: str) -> str:
        """Return the fragment at the end of `line`."""
        return self.engine.partial_at(line, len(line))

    def test_token_without_a_slash_is_reported_whole(self) -> None:
        """A plain token is replaced entirely, so all of it is reported."""
        self.assertEqual(self._partial("move fix-log"), "fix-log")

    def test_empty_token_reports_nothing(self) -> None:
        """A cursor past a space is starting a token, with nothing to replace."""
        self.assertEqual(self._partial("move "), "")

    def test_absolute_destination_reports_the_segment_alone(self) -> None:
        """The leading `/` stays in the line: only the board fragment is replaced."""
        self.assertEqual(self._partial("move fix-login-bug /op"), "op")

    def test_a_lone_slash_reports_nothing(self) -> None:
        """A slash with nothing after it leaves nothing to replace."""
        self.assertEqual(self._partial("move fix-login-bug /"), "")

    def test_column_segment_of_a_path(self) -> None:
        """Past the board's slash the column fragment alone is replaced."""
        self.assertEqual(self._partial("move fix-login-bug /ops/back"), "back")

    def test_path_argument_reports_its_last_segment(self) -> None:
        """A board/column/task path completes a segment at a time, as it always has."""
        self.assertEqual(self._partial("show my-project/in-p"), "in-p")


if __name__ == "__main__":
    unittest.main()
