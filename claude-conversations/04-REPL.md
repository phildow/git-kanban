# REPL

Date: 20260615_071522

ID: 76d119c8-bbe5-47c9-b73c-4bdd3326c057


**User**: [2026-06-14 10:16:36]

We've considered a CLI and a TUI front end. What would a REPL front end look like?

---


**Claude**: [2026-06-14 10:17:04]

 A REPL front end sits in an interesting middle ground between the CLI and TUI. Here's how it would fit into your architecture and what it would look like concretely.

## What a REPL looks like for this application

The basic loop is simple: print a prompt, read a line, parse and dispatch it, print the result, repeat. The key difference from a plain CLI is *persistent state* — the REPL holds a live `KanbanService` instance and an active context across commands, so you pay the startup cost once instead of on every invocation.

```
$ kanban repl

kanban> use my-project/todo
Active context: my-project/todo

kanban (my-project/todo)> task list
  1. Fix login bug         [high]  alice    due 2026-06-20
  2. Write API docs        [med]   bob      due 2026-06-25

kanban (my-project/todo)> task create "Add rate limiting" --priority high --assignee alice
Created: Add rate limiting [a3f9c2d1]

kanban (my-project/todo)> task move "Add rate limiting" in-progress
Moved to: my-project/in-progress

kanban (my-project/todo)> /history
  task list
  task create "Add rate limiting" --priority high --assignee alice
  task move "Add rate limiting" in-progress

kanban (my-project/todo)> /quit
```

The prompt itself carries context, which is the main UX win over raw CLI invocations.

## How it differs from CLI and TUI

| Dimension | CLI | REPL | TUI |
|---|---|---|---|
| Startup cost | Per invocation | Once | Once |
| State | None (flags only) | Held in Python objects | Held in Python objects |
| Output | Formatted strings to stdout | Same, but pageable | Widget-rendered |
| Discoverability | `--help` flags | `?` / tab-complete | Visual menus |
| Scriptability | Excellent (shell pipes) | Poor | None |
| SSH-friendly | Yes | Yes | Fragile |

The REPL shares its command parsing and output formatting code with the CLI — both call the same `KanbanService` methods and render the same dataclasses. The only new layer is the read-eval-print loop itself and a few REPL-specific meta-commands.

## What's new in the REPL layer

**Meta-commands** (prefixed with `/` to distinguish from kanban commands):

```
/help          — list commands
/history       — show command history
/clear         — clear screen
/context       — show active board/column
/quit or /exit — exit
```

**Tab completion** using Python's `readline` + `completer` interface — boards, columns, task titles, and flag names are all completable from the live index.

**Command history** persisted to `~/.kanban_history` via `readline.read_history_file` / `write_history_file`, so history survives across sessions.

**Paging** for long output, either via Python's `pydoc.pager` or by piping to `$PAGER` for `task list` results.

## Where it fits in your architecture

```
CLI        REPL        TUI (future)
  \          |          /
   ↓         ↓         ↓
      KanbanService
           ↓
      Domain Services
           ↓
       Repositories
           ↓
     Storage / Git
```

All three front ends are thin consumers of the same facade. The REPL class itself is probably 150–200 lines: a loop, a dispatcher that calls your existing CLI command functions, and readline setup. You're essentially re-using your entire CLI layer and wrapping it in `while True: input()`.

## Implementation sketch

```python
class KanbanRepl:
    def __init__(self, service: KanbanService):
        self.service = service
        self.context = ActiveContext()  # same object CLI uses
        self._setup_readline()

    def _setup_readline(self):
        readline.set_completer(self._completer)
        readline.parse_and_bind("tab: complete")
        history = Path("~/.kanban_history").expanduser()
        if history.exists():
            readline.read_history_file(history)

    def run(self):
        print("kanban repl — /help for commands, /quit to exit")
        while True:
            try:
                prompt = self._build_prompt()
                line = input(prompt).strip()
            except (EOFError, KeyboardInterrupt):
                self._quit()
                break

            if not line:
                continue
            if line.startswith("/"):
                self._handle_meta(line)
            else:
                self._dispatch(line)

    def _build_prompt(self):
        ctx = self.context.describe()   # e.g. "my-project/todo"
        if ctx:
            return f"kanban ({ctx})> "
        return "kanban> "

    def _dispatch(self, line):
        # Tokenise and hand off to the same Click/Typer commands
        # the CLI uses, capturing their output
        try:
            args = shlex.split(line)
            cli_main(args, standalone_mode=False)
        except SystemExit:
            pass
        except KanbanError as e:
            print(f"Error: {e}")
```

The `standalone_mode=False` trick (if you use Click) lets you call your CLI entry point programmatically without it calling `sys.exit`, so the loop continues cleanly after each command.

## When to add it

The REPL is the lowest-effort third front end. Since it re-uses your CLI command functions almost entirely, it's worth adding right after the CLI is stable — before the TUI — because it immediately improves the interactive development and testing experience for the application itself. You'll find yourself using it to explore edge cases, and it doubles as a demo mode for showing the tool to collaborators over SSH.

---


**User**: [2026-06-15 03:44:22]

Can I support tab completion for boards, columns, and tasks in the repl?

---


**Claude**: [2026-06-15 03:44:49]

 Yes, and it's quite straightforward with Python's `readline` library. The completer function gets called with the current word being typed and a state integer (0, 1, 2, ... for each successive match), and you return candidates based on what's already been typed on the line.

## How the completer works

```python
import readline
import shlex

class KanbanCompleter:
    def __init__(self, service: KanbanService):
        self.service = service

    def complete(self, text: str, state: int) -> str | None:
        if state == 0:
            self._matches = self._get_matches(text)
        try:
            return self._matches[state]
        except IndexError:
            return None

    def _get_matches(self, text: str) -> list[str]:
        line = readline.get_line_buffer()
        try:
            tokens = shlex.split(line)
        except ValueError:
            tokens = line.split()

        # If the line is empty or cursor is on first token, complete commands
        if not tokens or (len(tokens) == 1 and not line.endswith(" ")):
            return self._complete_command(text)

        command = tokens[0]
        already_typed = tokens[1:] if line.endswith(" ") else tokens[1:-1]

        return self._complete_argument(command, already_typed, text)
```

## Completing positional arguments by command

The core of the completer is a dispatch on the command name. Each branch inspects how many positional arguments have already been typed to know what slot it's filling.

```python
    def _complete_argument(
        self, command: str, already_typed: list[str], text: str
    ) -> list[str]:

        match command:
            case "use":
                return self._complete_path(text, depth="board_or_column")

            case "task":
                return self._complete_task_subcommand(already_typed, text)

            case "board":
                return self._complete_board_subcommand(already_typed, text)

            case "column":
                return self._complete_column_subcommand(already_typed, text)

            case "search" | "log" | "status":
                return []  # freetext or no positional args

            case _:
                return []
```

## Path completion: the interesting part

Your `[<board>/<column>/]<task>` path syntax means the completer needs to parse partial paths and offer the next segment.

```python
    def _complete_path(
        self, text: str, depth: str = "task"
    ) -> list[str]:
        """
        Complete a board/column/task path progressively.
        text might be "", "my-pro", "my-project/", "my-project/to", etc.
        """
        parts = text.split("/")

        if len(parts) == 1:
            # Completing the board segment
            boards = self.service.list_boards()
            candidates = [b.name for b in boards]
            if depth in ("column", "task"):
                # Also offer board/ with trailing slash to drill in
                candidates = [f"{b.name}/" for b in boards]
            return [c for c in candidates if c.startswith(text)]

        if len(parts) == 2:
            board_name, col_prefix = parts
            board = self._get_board(board_name)
            if board is None:
                return []
            columns = self.service.list_columns(board_name)
            if depth == "task":
                candidates = [f"{board_name}/{c.name}/" for c in columns]
            else:
                candidates = [f"{board_name}/{c.name}" for c in columns]
            return [c for c in candidates if c.startswith(text)]

        if len(parts) == 3 and depth == "task":
            board_name, col_name, task_prefix = parts
            tasks = self.service.list_tasks(board_name, col_name)
            candidates = [
                f"{board_name}/{col_name}/{t.title}" for t in tasks
            ]
            return [c for c in candidates if c.startswith(text)]

        return []
```

The trailing-slash trick is what makes the progressive drill-down feel natural — readline replaces the completed text in place, so completing `my-project/` leaves the cursor ready to type the column segment.

## Wiring it up

```python
def _setup_readline(self, completer: KanbanCompleter):
    readline.set_completer(completer.complete)
    readline.set_completer_delims(" \t\n")  # don't split on / or -
    readline.parse_and_bind("tab: complete")

    history = Path("~/.kanban_history").expanduser()
    if history.exists():
        readline.read_history_file(history)
    import atexit
    atexit.register(readline.write_history_file, history)
```

The `set_completer_delims` call is important: by default readline treats `/` as a delimiter, which would break path completion by only passing `todo` instead of `my-project/todo` as the `text` argument.

## A note on performance

The completer is called on every keypress, so `list_tasks()` on a large board could introduce noticeable lag. Two mitigations:

**Cache with a short TTL** — store the results of `list_boards()`, `list_columns()`, and `list_tasks()` for a second or two. In a REPL the user's board state isn't changing between keystrokes.

```python
from functools import lru_cache
from time import time

class KanbanCompleter:
    _cache: dict[str, tuple[float, list]] = {}
    _TTL = 2.0  # seconds

    def _cached(self, key: str, fn):
        now = time()
        if key in self._cache and now - self._cache[key][0] < self._TTL:
            return self._cache[key][1]
        result = fn()
        self._cache[key] = (now, result)
        return result
```

**Use the index** — once you add SQLite, completions become a fast indexed lookup rather than a filesystem scan, which eliminates the need for the TTL cache entirely.

## What it feels like

```
kanban> task move my-<TAB>
my-project/   ops/

kanban> task move my-project/<TAB>
my-project/todo/   my-project/in-progress/   my-project/done/

kanban> task move my-project/todo/<TAB>
my-project/todo/fix-login-bug        my-project/todo/write-api-docs

kanban> task move my-project/todo/fix-login-bug in-<TAB>
in-progress
```

The whole thing is maybe 100 lines of code on top of what you already have, and it makes the REPL feel genuinely polished.

---


**User**: [2026-06-15 07:10:36]

Modify the tab completion results for paths so if the board is part of the  command's path it is not included in the results and if the board/column is part of the command's path it is not included in the results

---


**Claude**: [2026-06-15 07:10:52]

 This means reading the active context before generating candidates and trimming the prefix from results — so the user completes into the *remaining* path segments only.

## Updated `_complete_path`

```python
def _complete_path(self, text: str, depth: str = "task") -> list[str]:
    """
    Complete a board/column/task path, stripping segments already
    provided by the active context from both the candidate prefix
    and the returned strings.
    """
    ctx = self.context  # ActiveContext with .board and .column

    # Determine which segments the context already provides
    ctx_board  = ctx.board  # str | None
    ctx_column = ctx.column # str | None, only set if board is also set

    parts = text.split("/")

    # --- BOARD segment ---
    if ctx_board is None:
        # No board in context: user must type it
        if len(parts) == 1:
            boards = self.service.list_boards()
            candidates = [f"{b.name}/" for b in boards]
            return [c for c in candidates if c.startswith(text)]

    # --- COLUMN segment ---
    # Resolve which board to look up columns for
    if ctx_board is None:
        # Board comes from the typed path
        if len(parts) < 2:
            return []
        board_name, *rest = parts
    else:
        # Board is already known from context; path starts at column
        board_name = ctx_board
        rest = parts  # parts[0] is the column prefix (or board/ prefix)

    if ctx_column is None:
        # User must supply the column
        if len(rest) == 1:
            col_prefix = rest[0]
            columns = self.service.list_columns(board_name)
            if depth == "column":
                candidates = [c.name for c in columns]
            else:
                candidates = [f"{c.name}/" for c in columns]
            return [c for c in candidates if c.startswith(col_prefix)]

    # --- TASK segment ---
    if depth != "task":
        return []

    # Resolve which column to look up tasks for
    if ctx_column is None:
        # Column comes from the typed path
        if len(rest) < 2:
            return []
        col_name, *task_parts = rest
    else:
        # Column is already known from context; path starts at task
        col_name = ctx_column
        task_parts = rest  # parts[0] is the task prefix

    task_prefix = task_parts[0] if task_parts else ""
    tasks = self.service.list_tasks(board_name, col_name)
    candidates = [t.title for t in tasks]
    return [c for c in candidates if c.startswith(task_prefix)]
```

## What changes

The logic resolves each path segment from either the active context or the typed text, in order. Once a segment is satisfied by context it's consumed silently — the user never types it and it never appears in completions.

```
# No active context
kanban> task move my-project/todo/<TAB>
my-project/todo/fix-login-bug    my-project/todo/write-api-docs

# After: use my-project
kanban (my-project)> task move todo/<TAB>
todo/fix-login-bug    todo/write-api-docs

# After: use my-project/todo
kanban (my-project/todo)> task move <TAB>
fix-login-bug    write-api-docs
```

The returned candidates are always relative to what the user still needs to type, which means the completed text is also shorter — `fix-login-bug` rather than `my-project/todo/fix-login-bug` — and the facade receives a partial path that it resolves the same way the CLI already does via your path resolution rules (explicit → active context → index).

---


**User**: [2026-06-15 07:13:28]

for tab completion if the board or column cannot be resolved from the user context (active context) resolve it from the path supplied by the user

---


**Claude**: [2026-06-15 07:14:16]

 That's already what the code does — but the current structure buries that logic in conditionals that make it hard to follow. Let me rewrite it so the resolution strategy is explicit and reads clearly.

## The idea

---


**User**: [2026-06-15 07:15:09]

show me what tab completion looks like when the board and column are resolved from the path so far supplied by the user if they cannot be resolved from the active context

---


**Claude**: [2026-06-15 07:15:22]

 Here's what the progression looks like in each context state:

## No active context

The user must type everything. Completions offer the next segment with a trailing slash to drill in.

```
kanban> task move <TAB>
my-project/   ops/

kanban> task move my-<TAB>
my-project/

kanban> task move my-project/<TAB>
todo/   in-progress/   in-review/   done/

kanban> task move my-project/to<TAB>
todo/

kanban> task move my-project/todo/<TAB>
fix-login-bug   write-api-docs   add-rate-limiting

kanban> task move my-project/todo/fix<TAB>
fix-login-bug
```

## Active board, no active column

The board segment is skipped. Completion starts at the column, resolved against the active board.

```
kanban (my-project)> task move <TAB>
todo/   in-progress/   in-review/   done/

kanban (my-project)> task move to<TAB>
todo/

kanban (my-project)> task move todo/<TAB>
fix-login-bug   write-api-docs   add-rate-limiting

kanban (my-project)> task move todo/fix<TAB>
fix-login-bug
```

## Active board and column

Both segments are skipped. Completion starts directly at the task title.

```
kanban (my-project/todo)> task move <TAB>
fix-login-bug   write-api-docs   add-rate-limiting

kanban (my-project/todo)> task move fix<TAB>
fix-login-bug
```

## The mixed case — user overrides context with an explicit path

This is the key behaviour your question is about. Even with an active context, if the user starts typing a path with a `/` in it, the completer detects that board (and column) are being supplied explicitly and resolves subsequent segments from what's been typed rather than from context.

```
# Active context is my-project/todo, but user is typing a path from ops/
kanban (my-project/todo)> task move ops/<TAB>
backlog/   todo/   in-progress/   done/

kanban (my-project/todo)> task move ops/in-pro<TAB>
in-progress/

kanban (my-project/todo)> task move ops/in-progress/<TAB>
deploy-staging   update-certs   rotate-keys

# Active context is my-project, user supplies board and column explicitly
kanban (my-project)> task move ops/todo/<TAB>
deploy-staging   update-certs   rotate-keys
```

The signal that the user is overriding context is simply the presence of a `/` in the typed text. One slash means they've supplied a board; two slashes means they've supplied both board and column. The completer counts slashes in `text` and uses that to decide how many context segments to ignore.

```python
parts = text.split("/")
slashes = len(parts) - 1

# slashes == 0: no path supplied yet, use full context
# slashes >= 1: board is from typed path, ignore ctx.board
# slashes >= 2: board + column from typed path, ignore both
```

---

