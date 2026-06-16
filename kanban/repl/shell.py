"""Minimal interactive REPL for kanban commands."""

from __future__ import annotations

import argparse
import shlex
import signal
from argparse import Namespace
from contextlib import contextmanager

from services.kanban import KanbanService

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
    """Return a prompt string that reflects the board and column context as a path."""
    return f"kanban ({svc.working_path}) > "


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


def _complete_path_tokens(text: str, tokens_before: list[str], svc: KanbanService) -> list[str]:
    """Complete path-like positional arguments for REPL commands."""
    if not tokens_before:
        return []

    command = tokens_before[0]

    if command in {"use", "cd"}:
        return svc.completions_for_path(text)

    if len(tokens_before) < 2:
        return []

    # defer to completions_for in all cases
    # and it is the responsibility of the service to sort -- just alpha-complete the raw completions_for_path results and return those, without filtering by prefix again here.

    # print(f"Completing path tokens for command: {command}, tokens_before: {tokens_before}, text: '{text}'")
    return svc.completions_for_path(text) 


def _complete_path_tokens_verb_first(text: str, tokens_before: list[str], svc: KanbanService) -> list[str]:    
    """Complete path-like positional arguments for verb-first REPL commands."""
    if not tokens_before:
        return []

    command = tokens_before[0]

    # defer to completions_for in all cases
    # and it is the responsibility of the service to sort -- just alpha-complete the raw completions_for_path results and return those, without filtering by prefix again here.

    if command in {"use", "cd"}:
        return svc.completions_for_path(text)

    if len(tokens_before) < 2:
        return []

    # print(f"Completing path tokens for command: {command}, tokens_before: {tokens_before}, text: '{text}'")
    return svc.completions_for_path(text)


def _resolve_board_column_path(path: str, svc: KanbanService) -> str:
    """Resolve a possibly relative column path into BOARD/COLUMN form."""
    if "/" in path:
        return path

    context = svc.user_context
    board = context.board
    if not board:
        raise ValueError("Board context is required for relative column paths")
    return f"{board}/{path}"


def _resolve_task_path(path: str, svc: KanbanService) -> str:
    """Resolve a task path into BOARD/COLUMN/TASK form using active context."""
    parts = path.split("/")
    if len(parts) >= 3:
        return path

    context = svc.user_context
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
        context = svc.user_context
        if context.board and context.column:
            return context.board
        if (context.board and not context.column) or (not context.board and not context.column):
            return "--clear"
    return normalized


# TODO: WTF does this even do?
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
            context = svc.user_context
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
                context = svc.user_context
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


# TODO: WTF does this even do?
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

    if command in {"list", "ls"}:
        if len(rewritten) >= 2:
            rewritten[1] = _resolve_use_path(rewritten[1], svc)
        return rewritten

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
    from cli.parser import build_parser as build_cli_parser
    from repl.parser import build_parser as build_repl_parser
    
    try:
        parser = build_cli_parser(enable_use=True) if noun_first else build_repl_parser(enable_use=True)
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
                    # args: Namespace = parser.parse_args(tokens)
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
