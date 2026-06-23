"""REPL completion tests for board/column path suggestions."""

from __future__ import annotations

import sys
import tempfile
import unittest

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

from cli.parser import build_parser as build_cli_parser
from models import UserContext
from repl.parser import build_parser as build_repl_parser
from repl.shell import (
    _prompt,
    run_repl,
)
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

    def change_dir(self, path=None, clear=False):
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
            return [f"{b.name}/" for b in self.get_boards() if b.name.startswith(path.name)]
        elif len(parts) == 2:
            board = parts[3]
            return [f"{c.name}/" for c in self.get_columns(board) if c.name.startswith(path.name)]
        elif len(parts) == 4:
            board, column = parts[1], parts[2]
            return [t.title for t in self.get_tasks(f"{board}/{column}") if t.title.startswith(path.name)]
        else:
            return []


    def get_boards(self):
        return [
            SimpleNamespace(name="main"),
            SimpleNamespace(name="infra"),
        ]

    def get_columns(self, board: str):
        columns = {
            "main": [
                SimpleNamespace(name="todo"),
                SimpleNamespace(name="triage"),
                SimpleNamespace(name="done"),
            ],
            "infra": [SimpleNamespace(name="backlog"), SimpleNamespace(name="wip")],
        }
        return columns[board]

    def get_tasks(self, path=None, **kwargs):
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
        temp_dir = Path(tempfile.gettempdir()) / f"kanban-{uuid4()}"
        temp_dir.mkdir()
        self.repo = InMemoryRepository(root=temp_dir)
        self.svc = KanbanService(
            repository=self.repo,
            index_service=IndexService(repository=self.repo),
            git_service=GitService(),
        )
        self.svc.create_board("alpha", columns=[])
        self.svc.create_column("alpha/todo")
        self.svc.create_column("alpha/done")
        self.svc.create_board("beta", columns=[])
        self.svc.create_column("beta/backlog")

    # TODO: Add partial command completions tests for the repl

class TestReplInterruptBehavior(unittest.TestCase):
    def test_ctrl_c_reprompts_instead_of_exiting(self):
        svc = _FakeSvc()
        renderer = MagicMock()

        svc.is_initialized = MagicMock(return_value=True)
        svc.kanban_dir = None

        with patch("builtins.input", side_effect=[KeyboardInterrupt(), "quit"]) as input_mock:
            with patch("builtins.print") as print_mock:
                run_repl(svc=svc, renderer=renderer)

        self.assertEqual(input_mock.call_count, 2)
        print_mock.assert_any_call("bye")       
        

if __name__ == "__main__":
    unittest.main()
