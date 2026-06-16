"""REPL completion tests for board/column path suggestions."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cli.parser import build_parser
from repl.shell import (
    _prompt,
    _rewrite_noun_first_relative_paths,
    _rewrite_verb_first_relative_paths,
    _complete_command_tokens,
    _complete_path_tokens,
    run_repl,
)
from repl.parser import build_parser as build_verb_first_parser
from models import UserContext
from services.kanban import KanbanService
from services.index import IndexService
from services.git import GitService 
from storage.memory import InMemoryRepository


class _FakeSvc:
    def __init__(self):
        self._ctx = SimpleNamespace(board="main", column="todo")

    @property
    def working_path(self) -> str:
        board = self._ctx.board
        column = self._ctx.column
        if board and column:
            return f"/{board}/{column}"
        if board:
            return f"/{board}"
        return "/"

    @property
    def user_context(self):
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

    def completions_for_path(self, text: str) -> list[str]:
        path = Path(self.working_path) / text
        parts = path.parts # ["/", board|None, column|None, title-or-id|None]

        if len(parts) == 2:
            return [f"{b.name}/" for b in self.list_boards() if b.name.startswith(path.name)]
        elif len(parts) == 2:
            board = parts[3]
            return [f"{c.name}/" for c in self.list_columns(board) if c.name.startswith(path.name)]
        elif len(parts) == 4:
            board, column = parts[1], parts[2]
            return [t.title for t in self.list_tasks(f"{board}/{column}") if t.title.startswith(path.name)]
        else:
            return []


    def list_boards(self):
        return [
            SimpleNamespace(name="main"),
            SimpleNamespace(name="infra"),
        ]

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
        self.repo = InMemoryRepository()
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
            user_context=UserContext(),
        )
        self.svc.create_board("alpha")
        self.svc.create_column("alpha/todo")
        self.svc.create_column("alpha/done")
        self.svc.create_board("beta")
        self.svc.create_column("beta/backlog")

    # TODO: Add partial command completions tests for the repl

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

        with patch("repl.parser.build_parser") as build_verb:
            with patch("cli.parser.build_parser") as build_noun:
                with patch("builtins.input", side_effect=["quit"]):
                    build_verb.return_value = build_parser(enable_use=True)
                    run_repl(svc=svc, renderer=renderer)

        build_verb.assert_called_once_with(enable_use=True)
        build_noun.assert_not_called()

    def test_run_repl_uses_noun_first_parser_when_requested(self):
        svc = _FakeSvc()
        renderer = MagicMock()

        with patch("repl.parser.build_parser") as build_verb:
            with patch("cli.parser.build_parser") as build_noun:
                with patch("builtins.input", side_effect=["quit"]):
                    build_noun.return_value = build_parser(enable_use=True)
                    run_repl(svc=svc, renderer=renderer, noun_first=True)

        build_noun.assert_called_once_with(enable_use=True)
        build_verb.assert_not_called()


if __name__ == "__main__":
    unittest.main()
