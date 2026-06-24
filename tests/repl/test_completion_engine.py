"""Tests for CompletionEngine, walking a fixture argparse tree.

The fixture parser mirrors the dest-naming conventions and nested
subcommand shape of the real ``repl.parser`` module (path/board/column
dests, nested "subject" subparsers, aliases, and choice-restricted
flags) without depending on its command-handler imports, so these
tests stay hermetic.

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

from repl.completion_engine import CompletionEngine

_NOOP = lambda args: None  # noqa: E731 - trivial stand-in for real handlers


def _build_fixture_parser() -> argparse.ArgumentParser:
    """Build a parser exercising every completion-relevant convention."""

    parser = argparse.ArgumentParser(add_help=False, prog="")
    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND")
    subparsers.required = True

    # cd: optional path
    p = subparsers.add_parser("cd")
    p.add_argument("path", nargs="?")
    p.set_defaults(func=_NOOP)

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
    p.add_argument("--assignee")
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

    # show: existing task path
    p = subparsers.add_parser("show", aliases=["view", "s"])
    p.add_argument("path")
    p.set_defaults(func=_NOOP)

    # move: task path + ambiguous destination (path-like per dest=="dest")
    p = subparsers.add_parser("move", aliases=["mv"])
    p.add_argument("path")
    p.add_argument("dest")
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

    # exit: aliases only, no arguments
    p = subparsers.add_parser("exit", aliases=["quit", ":q"])
    p.set_defaults(func=_NOOP)

    return parser


@dataclass(frozen=True)
class _Named:
    """Minimal stand-in for Board/Column with a `.name` attribute."""

    name: str


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

    def get_columns(self, board: str) -> list[_Named]:
        return [_Named(name) for name in self._BOARDS[board]]

    def get_tasks(self, path: str | None = None) -> list[_Task]:
        board, column, _ = self.path_components(path)
        if board is None or column is None:
            return []
        return [_Task(slug) for slug in self._BOARDS.get(board, {}).get(column, [])]

    def path_components(self, path: str | None = None) -> tuple[str | None, str | None, str | None]:
        """Resolve path against the stored user context, mirroring KanbanService."""
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
        self.assertEqual(self.complete("show /my-"), ["my-project/"])

    def test_lists_columns_after_board(self) -> None:
        self.assertEqual(
            self.complete("show /my-project/"),
            ["done/", "in-progress/", "in-review/", "todo/"],
        )

    def test_lists_tasks_after_column(self) -> None:
        self.assertEqual(
            self.complete("show /my-project/todo/"),
            ["add-rate-limiting", "fix-login-bug", "write-api-docs"],
        )

    def test_filters_tasks_by_prefix(self) -> None:
        self.assertEqual(self.complete("show /my-project/todo/fix"), ["fix-login-bug"])


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

    def test_leading_slash_overrides_context(self) -> None:
        context = _Context(board="my-project", column="todo")
        self.assertEqual(
            self.complete("show /ops/", context),
            ["backlog/", "done/", "in-progress/", "todo/"],
        )


class MoveDestCompletionTests(EngineTestCase):
    """move's second positional (dest="dest") gets path-style completion."""

    def test_completes_first_path_argument(self) -> None:
        self.assertEqual(self.complete("move "), ["my-project/", "ops/"])

    def test_completes_destination_argument(self) -> None:
        line = "move /my-project/todo/fix-login-bug "
        self.assertEqual(self.complete(line), ["my-project/", "ops/"])

    def test_destination_respects_context(self) -> None:
        context = _Context(board="my-project")
        line = "move todo/fix-login-bug "
        self.assertEqual(
            self.complete(line, context),
            ["done/", "in-progress/", "in-review/", "todo/"],
        )


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
        line = "create task /my-project/todo/new-task --assignee al"
        self.assertEqual(self.complete(line), [])

    def test_board_flag_completes_existing_boards(self) -> None:
        line = "search bug --board my-"
        self.assertEqual(self.complete(line), ["my-project"])


class FreeTextCompletionTests(EngineTestCase):
    """Positionals with no special dest name get no suggestions."""

    def test_search_query_has_no_suggestions(self) -> None:
        self.assertEqual(self.complete("search "), [])

    def test_rename_new_name_has_no_suggestions(self) -> None:
        self.assertEqual(self.complete("rename board my-project "), [])


if __name__ == "__main__":
    unittest.main()
