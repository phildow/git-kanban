"""
Pure tab-completion logic for the REPL.

:class:`CompletionEngine` walks the *actual* argparse parser tree (the
one built by ``repl.parser.build_parser()``) to discover commands,
aliases, flags, and positional arguments, rather than maintaining a
separate hand-written spec. The parser is the single source of truth
for the REPL's grammar; this module only adds the data-driven part
argparse has no concept of -- completing board/column/task names from
the kanban store.

Convention (matches the parser's own naming):
    - A positional or flag with ``dest in PATH_LIKE_DESTS`` completes as
      a full board/column/task path, walked against the active context,
      handled entirely by the service's own ``path_components`` 
      and ``get_boards/get_columns/get_tasks`` methods.
    - ``dest == "board"`` completes against existing board names.
    - ``dest == "column"`` completes against columns of the active
      board.
    - An action with ``choices`` set (e.g. ``--priority``) completes
      against those choices directly from the parser.
    - Anything else is free text: no suggestions.

No dependency on ``readline`` or any terminal lives here, so this stays
unit-testable with plain strings; :mod:`kanban.repl.readline_completer`
adapts it to readline's ``(text, state)`` protocol.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import shlex

from ..models import Slug
from ..protocols.sluggable import Sluggable
from ..protocols.completion_data_source import CompletionDataSource

# Positional/flag dest names that complete as a full board/column/task
# path rather than a single segment. "path" is the parser's own
# convention for fully-specified paths.
PATH_LIKE_DESTS = frozenset({"path"})
COL_LIKE_DESTS = frozenset({"column", "exclude_columns"})

class CompletionEngine:
    """Computes tab-completion candidates for a REPL input line.

    Args:
        service: Data source for board/column/task names. In production
            this is the KanbanService facade; tests can pass a fake.
        parser: The root argparse parser built by
            ``repl.parser.build_parser()``. Walked at completion time;
            never mutated.

    Note:
        Path completion always reads through ``service`` (the same
        calls the ``list`` command makes), per "the filesystem is the
        source of truth" -- there is no completion-specific cache here.

    TODO:
        Add a ``get_file_completions`` method to KanbanService with an
        option to query the SQLite index instead of the filesystem,
        once the index is in place, and call that here instead of
        get_boards/get_columns/get_tasks for better latency on large
        stores.
    """

    def __init__(self, service: CompletionDataSource, parser: argparse.ArgumentParser) -> None:
        self._service = service
        self._root = parser

    def complete(self, line: str, cursor: int) -> list[str]:
        """Return completion candidates for the token at ``cursor``.

        Args:
            line: The full current input line.
            cursor: Cursor offset into ``line``.

        Returns:
            Candidate strings, each a full replacement for the current
            partial token (not a suffix).
        """

        text = line[:cursor]
        tokens, partial = self._split_for_completion(text)

        parser, remaining, pending_subcommand = self._descend(self._root, tokens)

        if pending_subcommand is not None:
            if remaining:
                return []  # an already-typed subcommand token didn't match
            return self._matching(list(pending_subcommand.choices), partial)

        return self._leaf_completions(parser, remaining, partial)

    def partial_at(self, line: str, cursor: int) -> str:
        """Return the partial token the cursor sits in.

        Callers that splice a candidate back into the line need to know
        how much of it the candidate replaces. Readline works this out
        for itself; the TUI has to ask.
        """

        _, partial = self._split_for_completion(line[:cursor])
        return partial

    def _descend(
        self, parser: argparse.ArgumentParser, tokens: list[str]
    ) -> tuple[argparse.ArgumentParser, list[str], argparse._SubParsersAction | None]:
        """Consume tokens that select a nested subcommand.

        Recurses through ``create board``, ``rename column``, etc. by
        following the parser's own ``subparsers`` actions and their
        ``choices`` (which already include any ``aliases=`` passed to
        ``add_parser``).

        Returns:
            A tuple of: the parser to interpret remaining tokens
            against; the tokens not yet consumed by subcommand
            selection; and, if the *next* token should itself complete
            a subcommand name, the subparsers action to complete it
            against (otherwise ``None``).
        """

        subparsers_action = self._subparsers_action(parser)
        if subparsers_action is None:
            return parser, tokens, None
        if not tokens:
            return parser, tokens, subparsers_action
        head, *rest = tokens
        sub_parser = subparsers_action.choices.get(head)
        if sub_parser is None:
            return parser, tokens, subparsers_action
        return self._descend(sub_parser, rest)

    @staticmethod
    def _subparsers_action(
        parser: argparse.ArgumentParser,
    ) -> argparse._SubParsersAction | None:
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                return action
        return None

    def _leaf_completions(
        self,
        parser: argparse.ArgumentParser,
        tokens: list[str],
        partial: str,
    ) -> list[str]:
        """Complete a positional or flag for a leaf (non-subcommand) parser."""

        optionals = parser._get_optional_actions()

        if partial.startswith("-"):
            flags = [flag for action in optionals for flag in action.option_strings]
            return self._matching(flags, partial)

        previous = tokens[-1] if tokens else None
        if previous is not None:
            option = self._option_for_flag(optionals, previous)
            if option is not None and self._takes_value(option):
                return self._complete_for_action(option, partial)

        positionals = parser._get_positional_actions()
        index = self._count_positionals(optionals, tokens)
        if index >= len(positionals):
            return []
        return self._complete_for_action(positionals[index], partial)

    @staticmethod
    def _option_for_flag(
        optionals: list[argparse.Action], token: str
    ) -> argparse.Action | None:
        for action in optionals:
            if token in action.option_strings:
                return action
        return None

    @staticmethod
    def _takes_value(action: argparse.Action) -> bool:
        """Whether ``action`` consumes a following token as its value.

        ``store_true``/``store_false``/``help`` actions are defined
        with ``nargs=0``; everything else (plain values, ``append``,
        etc.) consumes one token.
        """

        return action.nargs != 0

    @classmethod
    def _count_positionals(cls, optionals: list[argparse.Action], tokens: list[str]) -> int:
        """Count positional (non-flag) tokens already typed.

        Tokens matching a known flag, and the value following it (if
        the flag takes one), are skipped. Unrecognized ``-``-prefixed
        tokens are skipped on their own rather than counted.
        """

        by_flag = {flag: action for action in optionals for flag in action.option_strings}
        count = 0
        skip_next = False
        for token in tokens:
            if skip_next:
                skip_next = False
                continue
            action = by_flag.get(token)
            if action is not None:
                skip_next = cls._takes_value(action)
                continue
            if token.startswith("-"):
                continue
            count += 1
        return count

    def _complete_for_action(self, action: argparse.Action, partial: str) -> list[str]:
        """Complete a value for ``action`` per the dest-naming convention."""

        if action.choices:
            return self._matching([str(choice) for choice in action.choices], partial)
        if action.dest in PATH_LIKE_DESTS and action.metavar == "TASK":
            return self._complete_task_slug(partial)
        if action.dest in PATH_LIKE_DESTS:
            return self._complete_path(partial)
        if action.dest == "board":
            return self._matching([b.slug for b in self._service.get_boards()], partial)
        if action.dest in COL_LIKE_DESTS:
            if self._service.working_board is None:
                return []
            return self._matching(
                [c.slug for c in self._service.get_columns(self._service.working_board)], partial
            )
        if action.dest == "tags" or action.metavar == "TAG":
            return self._matching(self._service.get_tags(self._service.working_board), partial)
        if action.dest == "assigned_to":
            return self._matching(
                self._service.get_assigned_tos(self._service.working_board), partial
            )
        return []  # free text: no suggestions

    @staticmethod
    def _matching(choices: list[str], partial: str) -> list[str]:
        """Return choices starting with ``partial``, sorted."""

        return sorted(c for c in choices if c.startswith(partial))

    @staticmethod
    def _split_for_completion(text: str) -> tuple[list[str], str]:
        """Split text-before-cursor into completed tokens and the partial.

        Falls back to a naive whitespace split if ``text`` has an
        unterminated quote (normal mid-typing state, e.g. typing a
        quoted task title), since shlex raises on that rather than
        treating it as a partial token.
        """

        if text == "" or text[-1].isspace():
            try:
                return shlex.split(text), ""
            except ValueError:
                return text.split(), ""
        try:
            tokens = shlex.split(text)
        except ValueError:
            tokens = text.split()
        if not tokens:
            return [], text
        return tokens[:-1], tokens[-1]

    def _complete_task_slug(self, token: str) -> list[str]:
        """Complete a bare task slug against every task in the active board.

        Commands whose target is a task (``show``, ``edit``, ``update``,
        ``move``, ``assign``) address it by slug alone, so completion lists
        task slugs across all columns of the active board rather than walking
        board/column segments. Any ``/`` in the token means the input is no
        longer a bare slug, so no candidates are returned.
        """

        if "/" in token:
            return []

        board = self._service.working_board
        if board is None:
            return []

        # Task slugs are unique board-wide, but de-dupe defensively so a stale
        # store never surfaces the same slug twice.
        slugs = {t.slug for t in self._service.get_tasks(Path(f"/{board}"))}
        return self._matching(list(slugs), token)

    def _complete_path(self, token: str) -> list[str]:
        """Complete a board/column/task path token.

        Only relative paths are supported: completion starts at whatever depth
        the service's own ``UserContext`` already fixes, by way of the
        service's ``path_components`` method. A leading ``/`` is not a valid
        REPL path, so tokens beginning with ``/`` produce no candidates.

        Returns bare segment names (e.g. ``"in-progress/"``), not the
        full path. ``/`` is configured as a readline word-break
        character (see ReplCompleter.install), so readline itself only
        ever replaces the fragment after the last ``/`` -- everything
        typed before it stays in the buffer untouched. That's what
        keeps the completion menu showing bare names while the
        resulting line still reads as a full path.
        """

        if token.startswith("/"):
            return []

        slash_idx = token.rfind("/")
        if slash_idx == -1:
            prefix, partial = "", token
        else:
            prefix, partial = token[: slash_idx + 1], token[slash_idx + 1:]

        board, column, _ = self._service.path_components(prefix or None)
        return self._walk(board, column, partial)

    def _walk(self, board: Slug | None, column: Slug | None, partial: str) -> list[str]:
        """Complete the level reached by ``(board, column)`` against ``partial``."""

        if board is None:
            names = [str(b.slug) for b in self._service.get_boards()]
            suffix = "/"
        elif column is None:
            names = [str(c.slug) for c in self._service.get_columns(board)]
            suffix = "/"
        else:
            names = [str(t.slug) for t in self._service.get_tasks(Path(f"/{board}/{column}"))]
            suffix = ""

        return [f"{name}{suffix}" for name in self._matching(names, partial)]
