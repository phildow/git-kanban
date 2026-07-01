"""Minimal interactive REPL for kanban commands."""

from __future__ import annotations

import argparse
import atexit
import logging
import shlex
import signal

from argparse import Namespace
from contextlib import contextmanager

from ..repl.completion_engine import CompletionEngine
from ..repl.parser import build_parser
from ..repl.readline_completer import ReplCompleter
from ..services.kanban import KanbanService
from ..storage.kanban import (
    BoardAlreadyExists,
    BoardNotFound,
    ColumnAlreadyExists,
    ColumnNotFound,
    TaskAlreadyExists,
    TaskNotFound,
)

try:
    import readline
except ImportError:  # pragma: no cover
    readline = None


class _ReplExit(Exception):
    """Internal sentinel exception used to terminate the REPL loop."""


def _is_exit_command(line: str) -> bool:
    """Return True when input matches a REPL exit command."""
    return line in {"quit", "exit", ":q"}


def _is_help_command(line: str) -> bool:
    """Return True when input matches a REPL help command."""
    return line in {"help", "h", "?"}


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


def _prompt(svc: KanbanService) -> str:
    """Return a prompt string that reflects the board and column context as a path."""
    return f"kanban ({svc.working_path}) > "


def _initialize_kanban(svc: KanbanService, renderer: object) -> bool:
    """Prompt the user to initialize a kanban repository if not already initialized."""
    if svc.is_initialized:
        return True

    root_dir = svc.root
    directory = root_dir.name

    print(f"No kanban repository found in {root_dir}.")
    should_init = input(f"Would you like to initialize kanban at {directory}? (y/N)) ").strip().lower()
    if should_init in {"y", "yes"}:
        try:
            svc.initialize_kanban()
            renderer.render_init(None, True)
            return True
        except Exception as exc:
            exc_desc = str(exc) or exc.__class__.__name__
            logging.error("Failed to initialize repository: %s", exc_desc)
            renderer.render_init(None, False)
            return False
    return False


@contextmanager
def _install_exit_signal_handlers():
    """
    Temporarily map common terminal exit key-signals to clean REPL shutdown.
    Keep Ctrl-C (`SIGINT`) for line cancellation/re-prompt behavior.
    """
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


def _print_welcome_message(svc: KanbanService) -> None:
    """Print a welcome message when the REPL starts."""
    if not svc.is_initialized:
        print("No kanban repository found in the current directory.")
        return

    context = svc.user_context
    board = context.board
    column = context.column

    context_str = f"/{board}/{column}" if board and column else f"/{board}" if board else "/"
    print(f"Welcome to the kanban REPL. Current context: {context_str}\nType 'help (h)' for usage, 'quit (:q)' to exit")


def _print_help_message(parser: argparse.ArgumentParser) -> None:
    """Print the help message for the REPL."""
    help_text = parser.format_help()
    help_text = help_text.replace("show this help message and exit", "Show this help message")
    help_text = help_text.replace("usage: COMMAND ...\n", "")
    print(help_text)


def _load_command_history(svc: KanbanService) -> None:
    """Return the command history from the REPL history file, if available."""
    if readline is None:
        return

    kanban_dir = svc.kanban_dir
    if not kanban_dir:
        return

    history_file = kanban_dir / "history"
    if not history_file.exists():
        return

    try:
        readline.read_history_file(str(history_file))
    except Exception as exc:
        exc_desc = str(exc) or exc.__class__.__name__
        logging.error("Failed to read REPL history file: %s", exc_desc)


def _save_command_history(svc: KanbanService) -> None:
    """Save the command history to the REPL history file."""
    if readline is None:
        return

    kanban_dir = svc.kanban_dir
    if not kanban_dir:
        return

    history_file = kanban_dir / "history"
    try:
        readline.write_history_file(str(history_file))
    except Exception as exc:
        exc_desc = str(exc) or exc.__class__.__name__
        logging.error("Failed to save REPL history file: %s", exc_desc)


def run_repl(*, svc: KanbanService, renderer: object) -> None:
    """Run a simple command loop that reuses the CLI parser/handlers."""

    if not _initialize_kanban(svc, renderer):
        exit(1)
    
    try:
        parser = build_parser()
        _configure_readline_shortcuts()

        engine = CompletionEngine(svc, parser)
        completer = ReplCompleter(engine)
        completer.install()
        
    except ValueError as exc:
        exc_desc = str(exc) or exc.__class__.__name__
        logging.error("Failed to initialize REPL: %s", exc_desc)
        print(f"Error: {exc}")

    _load_command_history(svc)
    atexit.register(lambda: _save_command_history(svc))

    _print_welcome_message(svc)

    # Ensure the index is up-to-date before starting the REPL (temporary measure until we have a persistent index)
    svc.index_service.rebuild()

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

                if _is_help_command(raw):
                    _print_help_message(parser)
                    continue

                try:
                    tokens = shlex.split(raw)
                    args: Namespace = parser.parse_args(tokens)
                except SystemExit:
                    # argparse already emitted a helpful message.
                    continue
                except Exception as exc:
                    exc_desc = str(exc) or exc.__class__.__name__
                    logging.error("Failed to parse command: %s", exc_desc)
                    print(f"Failed to parse command: {exc_desc}")
                    continue

                if not hasattr(args, "func"):
                    logging.error("No command handler registered for input: %s", raw)
                    print("No command handler registered")
                    continue

                try:
                    args.func(args, svc, renderer)
                except (BoardNotFound, ColumnNotFound, TaskNotFound) as exc:
                    logging.info(str(exc))
                    print(f"{exc}")
                except (BoardAlreadyExists, ColumnAlreadyExists, TaskAlreadyExists) as exc:
                    logging.info(str(exc))
                    print(f"{exc}")
                except ValueError as exc:
                    logging.error("ValueError: %s", str(exc))
                    print(f"{exc}")
                except KeyboardInterrupt:
                    print()
                    continue
                except Exception as exc:
                    exc_desc = str(exc) or exc.__class__.__name__
                    logging.error("Unexpected error: %s", exc_desc)
                    print(f"Unexpected error: {exc_desc}")
    except _ReplExit:
        print()

    print("bye")
