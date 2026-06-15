"""Minimal interactive REPL for kanban commands."""

from __future__ import annotations

import argparse
import shlex
import signal
from argparse import Namespace
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.kanban_service import KanbanService

try:
    import readline
except ImportError:  # pragma: no cover
    readline = None


def _is_exit_command(line: str) -> bool:
    """Return True when input matches a REPL exit command."""
    return line in {"quit", "exit", ":q"}


def _is_clear_screen_command(line: str) -> bool:
    """Return True when input represents a clear-screen control sequence."""
    # Ctrl+L emits ASCII form-feed in readline-backed terminals.
    return line in {"\x0c", "^L"}


def _clear_screen() -> None:
    """Clear the terminal using ANSI escape sequences."""
    # ANSI clear screen + move cursor to home.
    print("\033[2J\033[H", end="", flush=True)


def _configure_readline_shortcuts() -> None:
    """Best-effort keybindings for interactive convenience."""
    if readline is None:
        return

    try:
        doc = getattr(readline, "__doc__", "") or ""
        if "libedit" in doc:
            readline.parse_and_bind("bind ^I rl_complete")
            readline.parse_and_bind("bind ^L clear-screen")
            readline.parse_and_bind("set show-all-if-ambiguous on")
        else:
            readline.parse_and_bind("tab: complete")
            readline.parse_and_bind("Control-l: clear-screen")
            readline.parse_and_bind("set show-all-if-ambiguous on")
    except Exception:
        # Non-fatal: keep fallback handling in the input loop.
        return


def _starts_with(items: list[str], prefix: str) -> list[str]:
    """Return items that begin with the provided prefix."""
    return [item for item in items if item.startswith(prefix)]


def _safe_list_boards(svc: KanbanService) -> list[str]:
    """Best-effort board name lookup for completion helpers."""
    try:
        boards = svc.list_boards()
    except Exception:
        return []
    return [board.name for board in boards]


def _safe_list_columns(svc: KanbanService, board: str | None) -> list[str]:
    """Best-effort column name lookup for a board for completion helpers."""
    if not board:
        return []
    try:
        columns = svc.list_columns(board=board)
    except Exception:
        return []
    return [column.name for column in columns]


def _safe_list_task_names(svc: KanbanService, board: str | None, column: str | None) -> list[str]:
    """Best-effort task-name lookup for a board/column path."""
    if not board or not column:
        return []
    try:
        tasks = svc.list_tasks(path=f"{board}/{column}")
    except Exception:
        return []

    names: list[str] = []
    for task in tasks:
        slug = task.slug if getattr(task, "slug", None) else None
        title = task.title if getattr(task, "title", None) else None
        value = slug or title
        if value:
            names.append(value)

    return sorted(dict.fromkeys(names))

def _prompt(svc: KanbanService) -> str:
    """Build a prompt string that reflects the active board/column context."""
    context = svc.get_user_context()
    board = context.board
    column = context.column

    if board and column:
        return f"kanban ({board}/{column})> "
    if board:
        return f"kanban ({board})> "
    return "kanban> "


def _complete_board_or_column_path(text: str, svc: KanbanService) -> list[str]:
    """Complete BOARD/COLUMN path values."""
    boards = _safe_list_boards(svc)
    context = svc.get_user_context()
    context_board = context.board

    if "/" in text:
        board_prefix, column_prefix = text.split("/", 1)
        matching_boards = _starts_with(boards, board_prefix)
        if board_prefix in boards:
            columns = _safe_list_columns(svc, board_prefix)
            return [f"{board_prefix}/{column}" for column in columns if column.startswith(column_prefix)]
        return [f"{board}/" for board in matching_boards]

    results: list[str] = []
    if context_board:
        context_columns = _safe_list_columns(svc, context_board)
        results.extend(column for column in context_columns if column.startswith(text))

    results.extend(f"{board}/" for board in boards if board.startswith(text))
    return sorted(dict.fromkeys(results))


def _complete_board_or_board_column_path(text: str, svc: KanbanService) -> list[str]:
    """Complete BOARD or BOARD/COLUMN path values."""
    boards = _safe_list_boards(svc)
    if "/" in text:
        board_prefix, column_prefix = text.split("/", 1)
        if board_prefix in boards:
            columns = _safe_list_columns(svc, board_prefix)
            return [f"{board_prefix}/{column}" for column in columns if column.startswith(column_prefix)]
        return [f"{board}/" for board in boards if board.startswith(board_prefix)]

    board_paths = [f"{board}/" for board in boards if board.startswith(text)]

    context = svc.get_user_context()
    context_board = context.board
    context_columns = _safe_list_columns(svc, context_board)
    column_matches = [column for column in context_columns if column.startswith(text)]

    return sorted(dict.fromkeys(board_paths + column_matches))


def _complete_task_list_path(text: str, svc: KanbanService) -> list[str]:
    """Complete `task list` path according to active context rules."""
    boards = _safe_list_boards(svc)
    context = svc.get_user_context()
    context_board = context.board

    # Explicit override once a slash appears: BOARD/COLUMN resolution.
    if "/" in text:
        board_prefix, column_prefix = text.split("/", 1)
        if board_prefix in boards:
            columns = _safe_list_columns(svc, board_prefix)
            return [f"{board_prefix}/{column}/" for column in columns if column.startswith(column_prefix)]
            # return [f"{column}/" for column in columns if column.startswith(column_prefix)]
        return [f"{board}/" for board in boards if board.startswith(board_prefix)]

    # With active board, only columns are suggested.
    if context_board:
        columns = _safe_list_columns(svc, context_board)
        return [f"{column}/" for column in columns if column.startswith(text)]

    # Without context, user must start with board.
    return [f"{board}/" for board in boards if board.startswith(text)]


def _complete_task_path(text: str, svc: KanbanService) -> list[str]:
    """Complete task path segments according to active user context."""
    context = svc.get_user_context()
    context_board = context.board
    context_column = context.column

    slash_count = text.count("/")

    # Explicit override path handling.
    if slash_count >= 2:
        board, column, task_prefix = text.split("/", 2)
        tasks = _safe_list_task_names(svc, board, column)
        return [f"{board}/{column}/{task}" for task in tasks if task.startswith(task_prefix)]

    if slash_count == 1:
        board, column_prefix = text.split("/", 1)
        columns = _safe_list_columns(svc, board)
        return [f"{board}/{column}/" for column in columns if column.startswith(column_prefix)]

    # Context-based completion when no explicit slash is present.
    if context_board and context_column:
        tasks = _safe_list_task_names(svc, context_board, context_column)
        return [task for task in tasks if task.startswith(text)]

    if context_board:
        columns = _safe_list_columns(svc, context_board)
        return [f"{column}/" for column in columns if column.startswith(text)]

    boards = _safe_list_boards(svc)
    return [f"{board}/" for board in boards if board.startswith(text)]


def _find_subparser_action(parser: argparse.ArgumentParser):
    """Return the first subparser action for a parser, if present."""
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action
    return None


def _top_level_commands(parser: argparse.ArgumentParser) -> list[str]:
    """Return sorted top-level command names from the parser."""
    subparsers = _find_subparser_action(parser)
    if subparsers is None:
        return []
    return sorted(subparsers.choices.keys())


def _complete_command_tokens(
    text: str,
    tokens_before: list[str],
    parser: argparse.ArgumentParser,
) -> list[str]:
    """Complete command names (top-level and nested subcommands)."""
    if not tokens_before:
        return _starts_with(_top_level_commands(parser), text)

    if tokens_before[0] in {"use", "cd"}:
        return []

    command_chain = list(tokens_before)

    current = parser
    for token in command_chain:
        subparsers = _find_subparser_action(current)
        if subparsers is None:
            return []
        child = subparsers.choices.get(token)
        if child is None:
            return []
        current = child

    next_subparsers = _find_subparser_action(current)
    if next_subparsers is None:
        return []

    choices = sorted(next_subparsers.choices.keys())

    # Keep plural aliases parseable, but do not surface them via tab completion.
    if command_chain in (["list"], ["ls"]):
        choices = [choice for choice in choices if choice not in {"boards", "columns", "tasks"}]

    return _starts_with(choices, text)


def _complete_from_buffer(text: str, parser: argparse.ArgumentParser) -> list[str]:
    """Compute command completion candidates using the readline buffer state."""
    if readline is None:
        return []

    line = readline.get_line_buffer()
    begin = readline.get_begidx()
    before = line[:begin]

    try:
        tokens_before = shlex.split(before)
    except ValueError:
        tokens_before = before.strip().split()

    return _complete_command_tokens(text, tokens_before, parser)


def _complete_path_tokens(text: str, tokens_before: list[str], svc: KanbanService) -> list[str]:
    """Complete path-like positional arguments for REPL commands."""
    if not tokens_before:
        return []

    command = tokens_before[0]
    if command in {"use", "cd"}:
        return _complete_board_or_board_column_path(text, svc)

    if len(tokens_before) < 2:
        return []

    sub = tokens_before[1]

    if command == "column":
        if sub == "list" and len(tokens_before) == 2:
            boards = _safe_list_boards(svc)
            return [board for board in boards if board.startswith(text)]
        if sub in {"create", "rename", "reorder", "delete"} and len(tokens_before) == 2:
            return _complete_board_or_column_path(text, svc)

    if command == "task":
        if sub == "list" and len(tokens_before) == 2:
            return _complete_task_list_path(text, svc)

        # Compatibility path for readline setups that still split on '/':
        # e.g. "task list main/t" may arrive as tokens_before=["task", "list", "main/"]
        # and text="t". Return suffixes so replacement keeps the existing board prefix.
        if sub == "list" and len(tokens_before) >= 3 and tokens_before[2].endswith("/"):
            prefix = tokens_before[2]
            full_matches = _complete_task_list_path(f"{prefix}{text}", svc)
            suffix_matches = [match[len(prefix):] for match in full_matches if match.startswith(prefix)]
            return sorted(dict.fromkeys(suffix_matches))

        if sub in {"create", "show", "edit", "delete"} and len(tokens_before) == 2:
            return _complete_task_path(text, svc)

        # Compatibility path for readline setups that still split on '/':
        # e.g. "task create main/t" may arrive as tokens_before=["task", "create", "main/"]
        # and text="t". Return suffixes so replacement keeps the existing board prefix.
        if sub in {"create", "show", "edit", "delete"} and len(tokens_before) >= 3 and tokens_before[2].endswith("/"):
            prefix = tokens_before[2]
            full_matches = _complete_task_path(f"{prefix}{text}", svc)
            suffix_matches = [match[len(prefix):] for match in full_matches if match.startswith(prefix)]
            return sorted(dict.fromkeys(suffix_matches))

        if sub == "move":
            if len(tokens_before) == 2:
                return _complete_task_path(text, svc)
            if len(tokens_before) == 3:
                return _complete_board_or_column_path(text, svc)

    return []


def _complete_path_tokens_verb_first(text: str, tokens_before: list[str], svc: KanbanService) -> list[str]:
    """Complete path-like positional arguments for verb-first REPL commands."""
    if not tokens_before:
        return []

    command = tokens_before[0]
    if command in {"use", "cd"}:
        return _complete_board_or_board_column_path(text, svc)

    if len(tokens_before) < 2:
        return []

    subject = tokens_before[1]
    if subject == "boards":
        subject = "board"
    elif subject == "columns":
        subject = "column"
    elif subject == "tasks":
        subject = "task"

    if command in {"list", "ls"}:
        if subject == "column" and len(tokens_before) == 2:
            boards = _safe_list_boards(svc)
            return [board for board in boards if board.startswith(text)]
        if subject == "task" and len(tokens_before) == 2:
            return _complete_task_list_path(text, svc)
        if subject == "task" and len(tokens_before) >= 3 and tokens_before[2].endswith("/"):
            prefix = tokens_before[2]
            full_matches = _complete_task_list_path(f"{prefix}{text}", svc)
            suffix_matches = [match[len(prefix):] for match in full_matches if match.startswith(prefix)]
            return sorted(dict.fromkeys(suffix_matches))

    if command in {"create", "rename", "reorder", "delete"} and subject == "column":
        if len(tokens_before) == 2:
            return _complete_board_or_column_path(text, svc)

    if command in {"create", "show", "edit", "delete"} and subject == "task":
        if len(tokens_before) == 2:
            return _complete_task_path(text, svc)
        if len(tokens_before) >= 3 and tokens_before[2].endswith("/"):
            prefix = tokens_before[2]
            full_matches = _complete_task_path(f"{prefix}{text}", svc)
            suffix_matches = [match[len(prefix):] for match in full_matches if match.startswith(prefix)]
            return sorted(dict.fromkeys(suffix_matches))

    if command == "move" and subject == "task":
        if len(tokens_before) == 2:
            return _complete_task_path(text, svc)
        if len(tokens_before) == 3:
            return _complete_board_or_column_path(text, svc)

    return []


def _resolve_board_column_path(path: str, svc: KanbanService) -> str:
    """Resolve a possibly relative column path into BOARD/COLUMN form."""
    if "/" in path:
        return path

    context = svc.get_user_context()
    board = context.board
    if not board:
        raise ValueError("Board context is required for relative column paths")
    return f"{board}/{path}"


def _resolve_task_path(path: str, svc: KanbanService) -> str:
    """Resolve a task path into BOARD/COLUMN/TASK form using active context."""
    parts = path.split("/")
    if len(parts) >= 3:
        return path

    context = svc.get_user_context()
    board = context.board
    column = context.column

    if len(parts) == 2:
        if not board:
            raise ValueError("Board context is required for relative task paths")
        return f"{board}/{parts[0]}/{parts[1]}"

    if not board or not column:
        raise ValueError("Board/column context is required for relative task paths")
    return f"{board}/{column}/{parts[0]}"


def _strip_trailing_slash(path: str) -> str:
    """Return a path token without trailing slashes."""
    if path == "/":
        return path
    return path.rstrip("/")


def _resolve_use_path(path: str, svc: KanbanService) -> str:
    """Resolve special REPL shortcuts for `use` paths."""
    normalized = _strip_trailing_slash(path)
    if normalized == "..":
        context = svc.get_user_context()
        if context.board and context.column:
            return context.board
        if (context.board and not context.column) or (not context.board and not context.column):
            return "--clear"
    return normalized


def _rewrite_noun_first_relative_paths(tokens: list[str], svc: KanbanService) -> list[str]:
    """Rewrite noun-first REPL command tokens so relative paths become explicit paths."""
    if not tokens:
        return tokens

    command = tokens[0]
    rewritten = list(tokens)
    if command in {"use", "cd"}:
        if len(rewritten) >= 2:
            rewritten[1] = _resolve_use_path(rewritten[1], svc)
        return rewritten

    if command == "column" and len(rewritten) >= 2:
        sub = rewritten[1]
        if sub == "list" and len(rewritten) == 2:
            context = svc.get_user_context()
            board = context.board
            if not board:
                raise ValueError("Board context is required for `column list` without BOARD")
            rewritten.append(board)
        elif sub in {"create", "rename", "reorder", "delete"} and len(rewritten) >= 3:
            rewritten[2] = _strip_trailing_slash(rewritten[2])
            rewritten[2] = _resolve_board_column_path(rewritten[2], svc)

    if command == "task" and len(rewritten) >= 2:
        sub = rewritten[1]
        if sub == "list":
            if len(rewritten) == 2:
                context = svc.get_user_context()
                board = context.board
                column = context.column
                if board and column:
                    rewritten.append(f"{board}/{column}")
                elif board:
                    rewritten.append(board)
                else:
                    raise ValueError("Board context is required for `task list` without PATH")
            elif len(rewritten) >= 3:
                rewritten[2] = _strip_trailing_slash(rewritten[2])
                rewritten[2] = _resolve_board_column_path(rewritten[2], svc)
        elif sub in {"create", "show", "edit", "delete"} and len(rewritten) >= 3:
            rewritten[2] = _strip_trailing_slash(rewritten[2])
            rewritten[2] = _resolve_task_path(rewritten[2], svc)
        elif sub == "move" and len(rewritten) >= 4:
            rewritten[2] = _strip_trailing_slash(rewritten[2])
            rewritten[3] = _strip_trailing_slash(rewritten[3])
            rewritten[2] = _resolve_task_path(rewritten[2], svc)
            rewritten[3] = _resolve_board_column_path(rewritten[3], svc)

    return rewritten


def _rewrite_verb_first_relative_paths(tokens: list[str], svc: KanbanService) -> list[str]:
    """Rewrite verb-first REPL command tokens so relative paths become explicit paths."""
    if not tokens:
        return tokens

    command = tokens[0]
    rewritten = list(tokens)

    if command in {"use", "cd"}:
        if len(rewritten) >= 2:
            rewritten[1] = _resolve_use_path(rewritten[1], svc)
        return rewritten

    if command in {"list", "ls"} and len(rewritten) == 1:
        context = svc.get_user_context()
        board = context.board
        column = context.column

        if board and column:
            rewritten.extend(["task", f"{board}/{column}"])
        elif board:
            rewritten.extend(["column", board])
        else:
            rewritten.append("board")
        return rewritten

    if command in {"list", "ls"} and len(rewritten) >= 2:
        subject = rewritten[1]
        if subject == "boards":
            rewritten[1] = "board"
            subject = "board"
        elif subject == "columns":
            rewritten[1] = "column"
            subject = "column"
        elif subject == "tasks":
            rewritten[1] = "task"
            subject = "task"
        if subject == "column":
            if len(rewritten) == 2:
                context = svc.get_user_context()
                board = context.board
                if not board:
                    raise ValueError("Board context is required for `list column` without BOARD")
                rewritten.append(board)
            elif len(rewritten) >= 3:
                rewritten[2] = _strip_trailing_slash(rewritten[2])
        elif subject == "task":
            if len(rewritten) == 2:
                context = svc.get_user_context()
                board = context.board
                column = context.column
                if board and column:
                    rewritten.append(f"{board}/{column}")
                elif board:
                    rewritten.append(board)
                else:
                    raise ValueError("Board context is required for `list task` without PATH")
            elif len(rewritten) >= 3:
                rewritten[2] = _strip_trailing_slash(rewritten[2])
                rewritten[2] = _resolve_board_column_path(rewritten[2], svc)

    if command in {"create", "rename", "reorder", "delete"} and len(rewritten) >= 2:
        subject = rewritten[1]
        if subject == "column" and len(rewritten) >= 3:
            rewritten[2] = _strip_trailing_slash(rewritten[2])
            rewritten[2] = _resolve_board_column_path(rewritten[2], svc)

    if command in {"create", "show", "edit", "delete"} and len(rewritten) >= 2:
        subject = rewritten[1]
        if subject == "task" and len(rewritten) >= 3:
            rewritten[2] = _strip_trailing_slash(rewritten[2])
            rewritten[2] = _resolve_task_path(rewritten[2], svc)

    if command == "move" and len(rewritten) >= 2 and rewritten[1] == "task" and len(rewritten) >= 4:
        rewritten[2] = _strip_trailing_slash(rewritten[2])
        rewritten[3] = _strip_trailing_slash(rewritten[3])
        rewritten[2] = _resolve_task_path(rewritten[2], svc)
        rewritten[3] = _resolve_board_column_path(rewritten[3], svc)

    return rewritten


def _is_noun_first_parser(parser: argparse.ArgumentParser) -> bool:
    """Return True when parser top-level commands use noun-first structure."""
    top = set(_top_level_commands(parser))
    return bool({"board", "column", "task"} & top)

def _configure_readline_completion(parser: argparse.ArgumentParser, svc: KanbanService) -> None:
    """Register the readline completer backed by parser-aware suggestions."""
    if readline is None:
        return

    try:
        delimiters = readline.get_completer_delims().replace("/", "").replace("-", "")
        readline.set_completer_delims(delimiters)
    except Exception:
        pass

    noun_first = _is_noun_first_parser(parser)

    def _completer(text: str, state: int):
        line = readline.get_line_buffer()
        begin = readline.get_begidx()
        before = line[:begin]

        try:
            tokens_before = shlex.split(before)
        except ValueError:
            tokens_before = before.strip().split()

        matches = _complete_command_tokens(text, tokens_before, parser)
        if not matches:
            if noun_first:
                matches = _complete_path_tokens(text, tokens_before, svc)
            else:
                matches = _complete_path_tokens_verb_first(text, tokens_before, svc)

        if state < len(matches):
            return matches[state]
        return None

    try:
        readline.set_completer(_completer)
    except Exception:
        return


class _ReplExit(Exception):
    """Internal sentinel exception used to terminate the REPL loop."""


@contextmanager
def _install_exit_signal_handlers():
    """Temporarily map common terminal exit key-signals to clean REPL shutdown."""
    # Keep Ctrl-C (`SIGINT`) for line cancellation/re-prompt behavior.
    managed_signals = [signal.SIGTERM]

    if hasattr(signal, "SIGQUIT"):
        managed_signals.append(signal.SIGQUIT)
    if hasattr(signal, "SIGTSTP"):
        managed_signals.append(signal.SIGTSTP)

    previous_handlers: dict[signal.Signals, object] = {}

    def _exit_handler(signum, frame):
        _ = signum, frame
        raise _ReplExit()

    try:
        for sig in managed_signals:
            previous_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, _exit_handler)
        yield
    finally:
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


def run_repl(*, svc: KanbanService, renderer: object, noun_first: bool = False) -> None:
    """Run a simple command loop that reuses the CLI parser/handlers."""
    from cli.noun_first_parser import build_parser as build_noun_first_parser
    from cli.verb_first_parser import build_parser as build_verb_first_parser
    
    try:
        parser = build_noun_first_parser(enable_use=True) if noun_first else build_verb_first_parser(enable_use=True)
        rewrite = _rewrite_noun_first_relative_paths if noun_first else _rewrite_verb_first_relative_paths
        _configure_readline_shortcuts()
        _configure_readline_completion(parser, svc)
    except ValueError as exc:
        print(f"Value error: {exc}")

    print("kanban repl started. type 'help' for usage, 'quit' to exit.")

    try:
        with _install_exit_signal_handlers():
            while True:
                try:
                    raw = input(_prompt(svc)).strip()
                except EOFError:
                    print()
                    break
                except KeyboardInterrupt:
                    print()
                    continue

                if not raw:
                    continue

                if _is_clear_screen_command(raw):
                    _clear_screen()
                    continue

                if _is_exit_command(raw):
                    break

                if raw in {"help", "?"}:
                    parser.print_help()
                    continue

                try:
                    tokens = shlex.split(raw)
                    args: Namespace = parser.parse_args(rewrite(tokens, svc))
                except SystemExit:
                    # argparse already emitted a helpful message.
                    continue

                if getattr(args, "command", None) == "repl":
                    print("already in repl")
                    continue

                if not hasattr(args, "func"):
                    print("No command handler registered")
                    continue

                try:
                    args.func(args, svc, renderer)
                except ValueError as exc:
                    print(f"Value error: {exc}")
                except KeyboardInterrupt:
                    print()
                    continue
    except _ReplExit:
        print()

    print("bye")
