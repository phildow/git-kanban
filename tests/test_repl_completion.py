"""REPL completion tests for board/column path suggestions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
KANBAN_SRC = PROJECT_ROOT / "kanban"
if str(KANBAN_SRC) not in sys.path:
    sys.path.insert(0, str(KANBAN_SRC))

from repl.shell import (
    _prompt,
    _rewrite_noun_first_relative_paths,
    _rewrite_verb_first_relative_paths,
    _complete_path_tokens,
    _complete_task_list_path,
    _complete_task_path,
    _complete_command_tokens,
    _complete_board_or_board_column_path,
    _complete_board_or_column_path,
    run_repl,
)
from cli.noun_first_parser import build_parser
from cli.verb_first_parser import build_parser as build_verb_first_parser


class _FakeSvc:
    def __init__(self):
        self._ctx = SimpleNamespace(board="main", column="todo")

    def list_boards(self):
        return [
            SimpleNamespace(name="main"),
            SimpleNamespace(name="infra"),
        ]

    def get_user_context(self):
        return self._ctx

    def use(self, path=None, clear=False):
        if clear:
            self._ctx = SimpleNamespace(board=None, column=None)
            return self._ctx
        if path is None:
            return self._ctx
        if "/" in path:
            board, column = path.split("/", 1)
            self._ctx = SimpleNamespace(board=board, column=column)
        else:
            self._ctx = SimpleNamespace(board=path, column=None)
        return self._ctx

    def list_columns(self, board: str):
        columns = {
            "main": [
                SimpleNamespace(name="todo"),
                SimpleNamespace(name="triage"),
                SimpleNamespace(name="done"),
            ],
            "infra": [SimpleNamespace(name="backlog"), SimpleNamespace(name="wip")],
        }
        return columns[board]

    def list_tasks(self, path=None, **kwargs):
        _ = kwargs
        tasks = {
            "main/todo": [
                SimpleNamespace(slug="fix-login-bug", title="Fix login bug"),
                SimpleNamespace(slug="write-api-docs", title="Write API docs"),
                SimpleNamespace(slug="add-rate-limiting", title="Add rate limiting"),
            ],
            "infra/wip": [
                SimpleNamespace(slug="deploy-staging", title="Deploy staging"),
                SimpleNamespace(slug="update-certs", title="Update certs"),
                SimpleNamespace(slug="rotate-keys", title="Rotate keys"),
            ],
            "infra/todo": [
                SimpleNamespace(slug="deploy-staging", title="Deploy staging"),
                SimpleNamespace(slug="update-certs", title="Update certs"),
                SimpleNamespace(slug="rotate-keys", title="Rotate keys"),
            ],
        }
        return tasks.get(path, [])


class TestReplCompletion(unittest.TestCase):
    def setUp(self) -> None:
        self.svc = _FakeSvc()

    def test_complete_column_path_uses_user_context(self):
        suggestions = _complete_board_or_column_path("to", self.svc)
        self.assertIn("todo", suggestions)

    def test_complete_column_path_with_explicit_board(self):
        suggestions = _complete_board_or_column_path("main/t", self.svc)
        self.assertIn("main/todo", suggestions)
        self.assertIn("main/triage", suggestions)

    def test_complete_column_path_board_prefix(self):
        suggestions = _complete_board_or_column_path("in", self.svc)
        self.assertIn("infra/", suggestions)

    def test_complete_scope_path_suggests_only_board_slash(self):
        suggestions = _complete_board_or_board_column_path("ma", self.svc)
        self.assertIn("main/", suggestions)
        self.assertNotIn("main", suggestions)

    def test_complete_scope_path_with_board_and_column(self):
        suggestions = _complete_board_or_board_column_path("infra/w", self.svc)
        self.assertEqual(suggestions, ["infra/wip"])

    def test_complete_top_level_commands(self):
        parser = build_parser()
        suggestions = _complete_command_tokens("bo", [], parser)
        self.assertIn("board", suggestions)

    def test_complete_nested_subcommands(self):
        parser = build_parser()
        suggestions = _complete_command_tokens("cr", ["board"], parser)
        self.assertIn("create", suggestions)

    def test_complete_verb_first_list_hides_plural_aliases(self):
        parser = build_verb_first_parser()
        suggestions = _complete_command_tokens("", ["list"], parser)
        self.assertIn("board", suggestions)
        self.assertIn("column", suggestions)
        self.assertIn("task", suggestions)
        self.assertNotIn("boards", suggestions)
        self.assertNotIn("columns", suggestions)
        self.assertNotIn("tasks", suggestions)

        ls_suggestions = _complete_command_tokens("", ["ls"], parser)
        self.assertIn("board", ls_suggestions)
        self.assertIn("column", ls_suggestions)
        self.assertIn("task", ls_suggestions)
        self.assertNotIn("boards", ls_suggestions)
        self.assertNotIn("columns", ls_suggestions)
        self.assertNotIn("tasks", ls_suggestions)

    def test_complete_unknown_command_has_no_subcommands(self):
        parser = build_parser()
        suggestions = _complete_command_tokens("", ["unknown"], parser)
        self.assertEqual(suggestions, [])

    def test_complete_top_level_includes_repl_use(self):
        parser = build_parser(enable_use=True)
        suggestions = _complete_command_tokens("u", [], parser)
        self.assertIn("use", suggestions)

    def test_prompt_includes_context(self):
        self.assertEqual(_prompt(self.svc), "kanban (main/todo)> ")
        self.svc.use(path="main")
        self.assertEqual(_prompt(self.svc), "kanban (main)> ")

    def test_rewrite_relative_task_path(self):
        tokens = _rewrite_noun_first_relative_paths(["task", "show", "fix-parser"], self.svc)
        self.assertEqual(tokens, ["task", "show", "main/todo/fix-parser"])

    def test_rewrite_relative_column_list(self):
        tokens = _rewrite_noun_first_relative_paths(["column", "list"], self.svc)
        self.assertEqual(tokens, ["column", "list", "main"])

    def test_rewrite_task_list_from_context(self):
        tokens = _rewrite_noun_first_relative_paths(["task", "list"], self.svc)
        self.assertEqual(tokens, ["task", "list", "main/todo"])

    def test_rewrite_task_list_without_path_uses_board_when_no_column_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        tokens = _rewrite_noun_first_relative_paths(["task", "list"], self.svc)
        self.assertEqual(tokens, ["task", "list", "main"])

    def test_rewrite_task_list_without_path_raises_when_no_board_context(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        with self.assertRaises(ValueError):
            _rewrite_noun_first_relative_paths(["task", "list"], self.svc)

    def test_rewrite_use_strips_trailing_slash(self):
        tokens = _rewrite_noun_first_relative_paths(["use", "main/todo/"], self.svc)
        self.assertEqual(tokens, ["use", "main/todo"])

    def test_rewrite_use_parent_path_to_board_when_column_context_exists(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        tokens = _rewrite_noun_first_relative_paths(["use", ".."], self.svc)
        self.assertEqual(tokens, ["use", "main"])

    def test_rewrite_cd_parent_path_to_board_when_column_context_exists(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        tokens = _rewrite_noun_first_relative_paths(["cd", ".."], self.svc)
        self.assertEqual(tokens, ["cd", "main"])

    def test_rewrite_use_parent_path_clears_without_column_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        tokens = _rewrite_noun_first_relative_paths(["use", ".."], self.svc)
        self.assertEqual(tokens, ["use", "--clear"])

    def test_rewrite_use_parent_path_clears_without_any_context(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        tokens = _rewrite_noun_first_relative_paths(["use", ".."], self.svc)
        self.assertEqual(tokens, ["use", "--clear"])

    def test_rewrite_cd_parent_path_clears_without_any_context(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        tokens = _rewrite_noun_first_relative_paths(["cd", ".."], self.svc)
        self.assertEqual(tokens, ["cd", "--clear"])

    def test_rewrite_use_parent_path_to_board_when_column_context_exists_verb_first(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        tokens = _rewrite_verb_first_relative_paths(["use", ".."], self.svc)
        self.assertEqual(tokens, ["use", "main"])

    def test_rewrite_use_parent_path_clears_without_column_context_verb_first(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        tokens = _rewrite_verb_first_relative_paths(["use", ".."], self.svc)
        self.assertEqual(tokens, ["use", "--clear"])

    def test_rewrite_task_create_strips_trailing_slash(self):
        tokens = _rewrite_noun_first_relative_paths(["task", "create", "main/todo/fix-login-bug/"], self.svc)
        self.assertEqual(tokens, ["task", "create", "main/todo/fix-login-bug"])

    def test_rewrite_task_create_strips_trailing_slash_verb_first(self):
        tokens = _rewrite_verb_first_relative_paths(["create", "task", "main/todo/fix-login-bug/"], self.svc)
        self.assertEqual(tokens, ["create", "task", "main/todo/fix-login-bug"])

    def test_rewrite_list_tasks_plural_verb_first(self):
        tokens = _rewrite_verb_first_relative_paths(["list", "tasks"], self.svc)
        self.assertEqual(tokens, ["list", "task", "main/todo"])

    def test_rewrite_ls_tasks_plural_verb_first(self):
        tokens = _rewrite_verb_first_relative_paths(["ls", "tasks"], self.svc)
        self.assertEqual(tokens, ["ls", "task", "main/todo"])

    def test_rewrite_list_task_without_path_uses_board_when_no_column_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        tokens = _rewrite_verb_first_relative_paths(["list", "task"], self.svc)
        self.assertEqual(tokens, ["list", "task", "main"])

    def test_rewrite_ls_task_without_path_uses_board_when_no_column_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        tokens = _rewrite_verb_first_relative_paths(["ls", "task"], self.svc)
        self.assertEqual(tokens, ["ls", "task", "main"])

    def test_rewrite_list_without_args_uses_task_scope_when_board_and_column_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        tokens = _rewrite_verb_first_relative_paths(["list"], self.svc)
        self.assertEqual(tokens, ["list", "task", "main/todo"])

    def test_rewrite_list_without_args_uses_column_scope_when_board_only_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        tokens = _rewrite_verb_first_relative_paths(["list"], self.svc)
        self.assertEqual(tokens, ["list", "column", "main"])

    def test_rewrite_list_without_args_uses_board_scope_when_no_context(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        tokens = _rewrite_verb_first_relative_paths(["list"], self.svc)
        self.assertEqual(tokens, ["list", "board"])

    def test_rewrite_ls_without_args_uses_same_context_rules_as_list(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        tokens = _rewrite_verb_first_relative_paths(["ls"], self.svc)
        self.assertEqual(tokens, ["ls", "task", "main/todo"])

    def test_rewrite_task_list_strips_trailing_slash(self):
        tokens = _rewrite_noun_first_relative_paths(["task", "list", "main/todo/"], self.svc)
        self.assertEqual(tokens, ["task", "list", "main/todo"])

    def test_task_path_completion_without_context_starts_with_boards(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_task_path("", self.svc)
        self.assertIn("main/", suggestions)
        self.assertIn("infra/", suggestions)

    def test_task_path_completion_with_board_context_starts_with_columns(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        suggestions = _complete_task_path("", self.svc)
        self.assertIn("todo/", suggestions)
        self.assertIn("done/", suggestions)

    def test_task_path_completion_with_explicit_board_and_partial_column_keeps_board(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_task_path("main/t", self.svc)
        self.assertIn("main/todo/", suggestions)
        self.assertIn("main/triage/", suggestions)

    def test_task_path_completion_with_board_and_column_context_starts_with_tasks(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        suggestions = _complete_task_path("", self.svc)
        self.assertIn("fix-login-bug", suggestions)
        self.assertIn("write-api-docs", suggestions)

    def test_task_path_completion_explicit_path_overrides_context(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        suggestions = _complete_task_path("infra/wip/", self.svc)
        self.assertIn("infra/wip/deploy-staging", suggestions)
        self.assertIn("infra/wip/update-certs", suggestions)

    def test_task_path_completion_with_explicit_board_column_partial_task_keeps_prefix(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_task_path("main/todo/f", self.svc)
        self.assertEqual(["main/todo/fix-login-bug"], suggestions)

    def test_task_move_path_completion_uses_task_path_rules(self):
        self.svc._ctx = SimpleNamespace(board="main", column="todo")
        suggestions = _complete_path_tokens("", ["task", "move"], self.svc)
        self.assertIn("fix-login-bug", suggestions)

    def test_task_list_completion_with_board_context_shows_only_columns(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        suggestions = _complete_task_list_path("", self.svc)
        self.assertIn("todo/", suggestions)
        self.assertIn("done/", suggestions)
        self.assertNotIn("main/", suggestions)
        self.assertNotIn("infra/", suggestions)

    def test_task_list_completion_with_explicit_board_shows_columns(self):
        self.svc._ctx = SimpleNamespace(board="main", column=None)
        suggestions = _complete_task_list_path("main/", self.svc)
        self.assertIn("main/todo/", suggestions)
        self.assertIn("main/done/", suggestions)

    def test_task_list_completion_with_explicit_board_and_partial_column_keeps_board(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_task_list_path("main/t", self.svc)
        self.assertIn("main/todo/", suggestions)
        self.assertIn("main/triage/", suggestions)

    def test_task_list_completion_with_split_slash_token_returns_column_suffixes(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_path_tokens("t", ["task", "list", "main/"], self.svc)
        self.assertIn("todo/", suggestions)
        self.assertIn("triage/", suggestions)

    def test_task_list_completion_with_split_slash_token_unique_prefix(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_path_tokens("to", ["task", "list", "main/"], self.svc)
        self.assertEqual(["todo/"], suggestions)

    def test_task_create_completion_with_split_slash_token_returns_column_suffixes(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_path_tokens("t", ["task", "create", "main/"], self.svc)
        self.assertIn("todo/", suggestions)
        self.assertIn("triage/", suggestions)

    def test_task_create_completion_with_split_slash_token_unique_prefix(self):
        self.svc._ctx = SimpleNamespace(board=None, column=None)
        suggestions = _complete_path_tokens("to", ["task", "create", "main/"], self.svc)
        self.assertEqual(["todo/"], suggestions)


class TestReplInterruptBehavior(unittest.TestCase):
    def test_ctrl_c_reprompts_instead_of_exiting(self):
        svc = _FakeSvc()
        renderer = MagicMock()

        with patch("builtins.input", side_effect=[KeyboardInterrupt(), "quit"]) as input_mock:
            with patch("builtins.print") as print_mock:
                run_repl(svc=svc, renderer=renderer)

        self.assertEqual(input_mock.call_count, 2)
        print_mock.assert_any_call("bye")

    def test_run_repl_uses_verb_first_parser_by_default(self):
        svc = _FakeSvc()
        renderer = MagicMock()

        with patch("cli.verb_first_parser.build_parser") as build_verb:
            with patch("cli.noun_first_parser.build_parser") as build_noun:
                with patch("builtins.input", side_effect=["quit"]):
                    build_verb.return_value = build_parser(enable_use=True)
                    run_repl(svc=svc, renderer=renderer)

        build_verb.assert_called_once_with(enable_use=True)
        build_noun.assert_not_called()

    def test_run_repl_uses_noun_first_parser_when_requested(self):
        svc = _FakeSvc()
        renderer = MagicMock()

        with patch("cli.verb_first_parser.build_parser") as build_verb:
            with patch("cli.noun_first_parser.build_parser") as build_noun:
                with patch("builtins.input", side_effect=["quit"]):
                    build_noun.return_value = build_parser(enable_use=True)
                    run_repl(svc=svc, renderer=renderer, noun_first=True)

        build_noun.assert_called_once_with(enable_use=True)
        build_verb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
