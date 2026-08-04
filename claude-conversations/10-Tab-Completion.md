# Tab Completion

Date: 20260620_100933

ID: 13e39a8c-ffd9-4d7d-97ed-b7628f0ecdc7


**User**: [2026-06-20 02:07:57]

The REPL supports tab completion. I'd like to review the design for tab completion and start implementing it.

---


**Claude**: [2026-06-20 02:08:59]

Before implementation, a few things in the spec need resolving — some are genuine ambiguities, one is a contradiction I want to flag.

**Contradiction: filenames vs. slugs**

The architecture says *"the task's filename is its title"*, and the metadata example has a separate `slug` field. But the tab-completion examples show directory listings like:

```
fix-login-bug   write-api-docs   add-rate-limiting
```

These look like slugs, not literal titles (`Fix login bug.md` would have spaces and capitals). This matters for completion because:
- If filenames are literal titles, completion must handle spaces — quoting/escaping in the REPL line parser, multi-word token matching, etc.
- If filenames are slugs, completion is simpler (no spaces ever), but then "filename is the title" is inaccurate — the slug is.

**Open design questions**

1. **Completion backend**: `readline` (stdlib, simple, function-based `(text, state)` callback, no native async, weak Windows support) vs `prompt_toolkit` (richer multi-column completions with descriptions, async-friendly, but it's a new dependency and changes how the whole REPL loop is built, not just completion).

2. **Where completion logic lives**: For testability (per your unit-test guidance), I'd want a pure function/class — e.g. `CompletionEngine.complete(line: str, cursor: int, context: UserContext) -> list[Completion]` — that's independent of readline/prompt_toolkit, with a thin adapter wiring it to whichever library we pick. This needs sign-off since it adds a layer not in the original architecture doc (it would sit beside the REPL's renderer, calling KanbanService).

3. **Data source for path completion**: should completion call `KanbanService` the same way `list` commands do (full filesystem scan-on-demand per keystroke), or should it go through `SearchService`/index? Given "index is always a cache," I'd default to going through KanbanService like any other read, but per-keystroke filesystem scans could feel laggy on large boards.

4. **Command-argument completion spec**: the REPL's verb-first grammar means `new <TAB>` should suggest `board|column|task` (entity keywords), while `move <TAB>` should suggest task paths. That implies a static per-command "argument shape" table (path vs. keyword vs. flag vs. free text) that the completer consults. Confirm this is the right model before I build it.

5. **Flag completion**: should `--pri<TAB>` complete to `--priority`? Spec doesn't show it explicitly but it's implied by "complete commands or files." Worth confirming in scope.

---


**User**: [2026-06-20 02:12:42]

Q: Are task filenames the literal title (with spaces/capitals) or a slugified version?
A: Slug (e.g. 'fix-login-bug.md')

Q: Which completion backend should the REPL use?
A: stdlib readline

---


**Claude**: [2026-06-20 02:13:23]

Noted — filenames are slugs; title is separate display metadata. That also implies the `rename` command needs to decide whether renaming changes the slug (and thus the file/path used by completion and any existing references). Worth resolving before we implement `task rename`/`board rename`, but it doesn't block tab completion design, so I'll set it aside for now.

With `readline` chosen, here's the completion design:

**1. Delimiter configuration**

`readline`'s default word-break characters include `/` and other punctuation, which would break path/slug tokens apart. I'd set:

```python
readline.set_completer_delims(" \t\n")
```

So the "current word" readline hands to the completer is the whole `/`-and-`-`-containing token (e.g. `/my-project/todo/fix`), and we do all path-segment parsing ourselves.

**2. Two-layer structure**

- `CompletionEngine` — pure, unit-testable, no readline dependency:
  `complete(line: str, cursor: int, context: UserContext) -> list[str]`
  Tokenizes the line (reusing the REPL's own command tokenizer, so completion and execution agree on parsing), identifies the command, which argument slot the cursor is in, and dispatches to a keyword completer, path completer, or flag completer.
- `ReplCompleter` — thin adapter implementing readline's `(text, state)` protocol, calling `get_line_buffer()`/`get_begidx()` and delegating to `CompletionEngine`.

This keeps completion logic testable with plain strings/fixtures, no real terminal needed.

**3. Per-command argument spec**

A static table (new module, e.g. `kanban/repl/completion_spec.py`) describing each command's argument slots as one of:
- `Keyword(choices)` — e.g. `new <TAB>` → `board|column|task`
- `Path(kind)` — board/column/task path completion per the context rules in the spec
- `Option(name, value_choices=None)` — flags like `--priority`, with optional value completion (`low|medium|high`)
- `FreeText` — no completion (e.g. a new task's title)

**4. Path completion data source**

Defaults to calling `KanbanService` the same way `list` commands do (live filesystem read each call), consistent with "filesystem is the source of truth" — no separate caching for completion. Latency is a known tradeoff of scan-on-demand and can be revisited once the SQLite index lands.

**5. Flag completion**

In scope: `--pri<TAB>` → `--priority`, and value completion for flags with closed choice sets, driven by the same per-command spec.

Want me to proceed with this, or adjust anything first?

---


**User**: [2026-06-20 02:19:44]

The two-layer structure and per-command argument spec look good, and yes we do want flag completion. As for the path completion data source let's use the kanban service list (get) commands for now, but make a note to add a get_file_completions method for later that has the option to query the index.

---


**Claude**: [2026-06-20 02:20:02]

Noted — I'll track that as a TODO comment in the path-completion code, flagging that `KanbanService` should later gain a `get_file_completions` method with an option to query the index instead of the filesystem.

One practical question before I start: there's no project scaffold yet (empty container — no `pyproject.toml`, no `kanban` package, no `KanbanService`). Tab completion's path/keyword logic needs *something* to call for board/column/task names. Two ways to sequence this:

1. **Scaffold the full skeleton first** — `pyproject.toml`, package layout, a minimal `KanbanService` facade with stub `list_boards`/`list_columns`/`list_tasks` methods (even if they just return empty lists or hit a not-yet-built repository), then build completion against it.
2. **Build completion against a `Protocol`** — define the minimal interface completion needs (e.g. `list_boards() -> list[str]`, `list_columns(board) -> list[str]`, `list_tasks(board, column) -> list[str]`) as a typing `Protocol`, build and unit-test `CompletionEngine` against a fake/mock implementing that Protocol, and defer wiring to the real `KanbanService` until it exists.

(2) lets us finish and fully test the completion engine in isolation now; (1) gets the real scaffold moving but means completion work is blocked on/intertwined with broader scaffolding decisions (storage, repositories, etc.) that haven't been discussed yet.

Which would you like?

---


**User**: [2026-06-20 02:23:32]

I already have a project that you do not have the full context for, and the kanban service is already implemented with get_boards, get_columns, and get_tasks methods. Assume those methods exist in the service layer and write the command against them. There is also already a REPL that is ready to work with readline.

---


**Claude**: [2026-06-20 02:23:42]

The user is telling me to assume these KanbanService methods already exist in their project even though I don't have access to the files, so I should write code that works with those existing methods without needing to see their implementation.

Now I need to figure out what these methods return — whether they're domain objects like Board, Column, and Task with attributes like name or title, or just strings. Based on the architecture principle of

---


**User**: [2026-06-20 02:24:12]

I already have a project that you do not have the full context for, and the kanban service is already implemented with get_boards, get_columns, and get_tasks methods. Assume those methods exist in the service layer and write the CompletionEngine methods against them. There is also already a REPL that is ready to work with readline.

---


**Claude**: [2026-06-20 02:27:37]

Building this with the assumptions below — flag anything that doesn't match your actual code:

- `KanbanService.get_boards()/get_columns(board)/get_tasks(board, column)` return objects with `.name` (Board/Column) and `.slug` (Task) attributes.
- `UserContext` has `.board: str | None` and `.column: str | None`.
- No existing shared tokenizer was specified, so I wrote a small one — swap it for the REPL's existing tokenizer if it has one, so completion and execution parse identically.

Now tests, using a fake service that mirrors the example boards/columns/tasks from the design doc:

That's a bug in the test, not the engine — `mv` legitimately starts with `m` too. Fixing the assertion:

All 24 tests pass, covering every example from the design spec. Copying to outputs:

Four files, ready to drop into your tree at `kanban/repl/` and `tests/repl/`. All 24 unit tests pass, covering every example case from the design discussion (no-context, board-context, board+column-context, override, keywords, flags).

Two things worth a look before you wire it in:

1. **`ALIASES` in `completion_spec.py` is static** — it only has the built-in defaults (`new`, `mv`, `rm`, etc.). If your REPL lets users redefine/add aliases at runtime, completion needs to read the live alias map instead of this hardcoded one, or the two will drift.
2. **Attribute names are guessed** (`Board.name`, `Column.name`, `Task.slug`) — if your actual dataclasses differ, it's a one-line fix in `_walk()` inside `completion_engine.py`.

The `get_file_completions`/index TODO is recorded as a docstring note on `CompletionEngine`. No CLAUDE.md changes needed — this adds infrastructure, not new commands.

---


**User**: [2026-06-20 02:31:49]

The commands, available flags, and arguments including path are already defined by a parser. Can we use the parser as the source of truth for the completion spec instead of redefining it?

---


**Claude**: [2026-06-20 02:32:03]

Possible, but I need to know the shape of that parser to introspect it correctly. A few things determine how:

1. **What library/structure is it?** (`argparse` with subparsers, `click`, a custom dataclass-based registry, something else?)
2. **How are "path" arguments distinguished from plain strings?** `argparse` (and most parsers) don't have a built-in concept of "this string completes against the kanban store" — so something has to mark it: a custom argument type/class, a naming convention (e.g. `dest="path"`), a metavar, or similar. What does yours use?
3. **How are closed-choice flags expressed?** (e.g. `argparse`'s `choices=("low","medium","high")` on `--priority` — if so, I can read that directly and `OptionSpec.choices` disappears entirely as a hand-maintained list.)

If you can show me the actual parser module (or the relevant subcommand definitions), I can map directly off it rather than guessing the introspection logic.

---


**User**: [2026-06-20 02:36:07]

1) We're using argparse 2) when the  parser expects a path argument it names it "path" 3) yes we use  `choices=`  to give the options. I've attached the current REPL parser.

---


**Claude**: [2026-06-20 02:38:14]

The parser's nested subparsers (`create_subject`, `rename_subject`, etc.) and the `choices=` already on the subparsers actions mean argparse can supply command names *and* aliases directly — `exit`'s `aliases=["quit", ":q"]` shows up automatically as a valid choice. So the static `ALIASES`/`COMMAND_SPECS` tables go away entirely; the engine just walks the live parser tree.

One real gap: `move`'s second positional, `dest` (help: *"destination (column, board, or new title)"*), isn't named `path`, `board`, or `column`, so under your naming convention it gets no completion as-is.

---


**User**: [2026-06-20 02:41:51]

Q: How should move's 'dest' argument be completed?
A: Treat it like 'path' (multi-segment board/column completion)

---


**Claude**: [2026-06-20 02:45:02]

Good — extending the convention so `dest in {"path", "dest"}` triggers path completion. Rewriting the engine to walk the live parser tree instead of a hand-maintained spec table; `completion_spec.py` is no longer needed since argparse's subparsers `choices` already give us command names and aliases directly (e.g. `exit`'s `aliases=["quit", ":q"]` shows up for free).

One thing worth flagging rather than deciding silently: for `create board <BOARD>` the `board` dest is a *new* name, but my rule completes `dest == "board"` against *existing* board names uniformly (same as `rename board`, where it correctly refers to an existing one). Suggesting existing names while naming something new is harmless and arguably helps avoid collisions, but say so if you'd rather it stayed silent for creation commands specifically.

Now update the readline adapter (constructor now needs a parser too) and rewrite the tests against a fixture parser shaped like the real one:

This one doesn't need changes — it already just takes a constructed `CompletionEngine`, and the parser now lives inside the engine. Good as-is. Now the tests, rebuilt against a fixture parser shaped like the real one:

The engine's right, my test expectations were wrong — `board`/`column` commands take a single, complete name (nothing to drill into further), so no trailing slash, unlike path segments. Fixing the assertions:

All 27 pass. Copying to outputs:

`completion_spec.py` is deleted; `CompletionEngine` now takes your `build_parser()` result directly and walks it. 27 tests pass against a fixture parser shaped like yours.

Wiring it up: `CompletionEngine(kanban_service, build_parser())` — same `parser` instance the REPL already uses to parse/dispatch, just also handed to the completer.

Things worth a second look:

1. **Relies on argparse internals** — `_get_optional_actions()`, `_get_positional_actions()`, `_SubParsersAction`, `parser._actions`. All underscore-prefixed, not public API, though stable for a very long time and the standard approach tools like `argcomplete` also use. Worth knowing if you ever pin/audit against argparse internals changing.
2. **`PATH_LIKE_DESTS = {"path", "dest"}`** is the one place completion extends your naming convention beyond what's already in the parser. If another ambiguous-shaped arg shows up later, it goes here.
3. Flag-value completion now also applies the `board`/`column`/path convention to **option** dests, not just positionals (e.g. `search --board <TAB>` completes existing boards) — this wasn't explicitly stated as in-scope but follows the same rule uniformly.
4. `create board <BOARD>` still suggests existing names (flagged earlier, unchanged — let me know if you want creation commands to suppress that).

---


**User**: [2026-06-20 02:56:38]

How do I use the ReplCompleter class?

---


**Claude**: [2026-06-20 02:56:46]

`ReplCompleter` wraps a `CompletionEngine` and wires it into `readline` for the session. Three steps:

1. **Construct the engine and completer once**, when the REPL starts:

```python
from kanban.repl.completion_engine import CompletionEngine
from kanban.repl.readline_completer import ReplCompleter
from repl.parser import build_parser

engine = CompletionEngine(kanban_service, build_parser())
completer = ReplCompleter(engine, get_context=lambda: user_context)
completer.install()
```

`get_context` is a zero-arg callable, not a value — pass a lambda (or bound method) that reads your REPL's *current* `UserContext` each time it's called, e.g. `lambda: self.user_context`. Don't pass `user_context` itself, since context changes after `cd`/`board`/`column` and the completer needs the live object, not a snapshot from startup.

2. **`install()` registers it with `readline`** — sets word-break delimiters and binds Tab. Call it once, before the input loop starts.

3. **Run the REPL loop as normal** — once installed, `readline` calls the completer automatically whenever the user presses Tab inside `input()`:

```python
while True:
    line = input(prompt)
    ...
```

Nothing else needs to call `ReplCompleter` directly — `complete()` isn't invoked by your code, it's invoked by `readline` itself via `__call__`.

One thing to confirm: does your REPL loop use plain `input()`, or something else (e.g. `prompt_toolkit`, a custom loop)? `readline.set_completer` only intercepts Tab inside `input()` — if the REPL reads lines another way, `install()` won't take effect.

---


**User**: [2026-06-20 02:59:07]

The REPL loop uses plain input

---


**Claude**: [2026-06-20 02:59:11]

Then `install()` is sufficient — no further wiring needed beyond the call shown above.

One thing to double check on your end: `readline` patches `input()` process-wide, so call `completer.install()` exactly once, before the loop starts (not per-iteration), or you'll keep re-registering the same completer pointlessly. If the REPL ever spins up more than one `input()`-based session in the same process (tests, nested shells, etc.), each would share that one global completer, so the `get_context` callable needs to resolve to whichever session is currently live — fine for a single REPL instance, just flagging it as a constraint if that ever changes.

Anything else to wire up, or is this ready to drop in?

---


**User**: [2026-06-20 03:43:41]

We use paths for a number of command arguments. the paths can include subfolders, eg board/column or board/comun/task and can begin with a forward slash,  requiring an absolute eg /board or /board/column. When completing a path the completion engine will replace the portion of the path that has already been typed or completed with the newly completed portion.

For example if I provide a path argument of "/ma" and press tab the engine correctly completes it to "/main". But if I continue into the folder to tab complete a board, for example "/main/to" with only a single board completion "todo", when I tab to complete it, the completion rewrites the written text to "todo" instead of preserving the previously typed portion of the path so that i see "/main/todo"

---


**Claude**: [2026-06-20 03:46:06]

Good catch — that's a real bug. The fix has to live in `_complete_path`: `_walk` only returns the matched *segment*, but since readline replaces the entire typed token (everything since the last whitespace, per our delimiter config), the candidate has to be the **full reconstructed token** — typed prefix included — not just the newly-matched piece. The single-segment case only looked correct because there was no prefix to lose; multi-segment exposed it.

Now updating the tests that previously asserted bare segment names for multi-segment cases — those expectations were wrong (they'd have shown the same dropped-prefix bug in a real terminal):

Now rewriting the test expectations to reflect full reconstructed paths:

All 27 pass. Syncing to outputs:

Fixed in `_complete_path`: it now reconstructs the full token (typed prefix + matched segment + trailing slash where applicable) instead of returning the bare segment name, since readline replaces the whole token, not just the part after the last `/`. The single-segment case only ever looked correct because there was no prefix to lose — it had the same bug, just invisibly.

---


**User**: [2026-06-20 03:50:00]

This is not what I want either. I'd like the command completion engine to work like it does on the command line. If we're already specifying for example the parent folder, the potential completions shouldn't include it. For example, if I type /main/in- the potential completion should be in-progress and in-review, not /main/in-progress and /main/in-review. However, when I accept the completion the result should include the text I've already typed: /main/in-progress

---


**Claude**: [2026-06-20 03:52:06]

I had it backwards. The actual fix belongs in the readline delimiter configuration, not in reconstructing paths by hand — that's exactly how shells do this themselves: `/` is a word-break character, so readline only ever replaces the fragment *after* the last `/`, leaving everything before it untouched in the buffer. That naturally gives bare names in the completion menu and a full path on insertion, for free. Reverting `_complete_path` and fixing the delimiters instead:

Now the readline adapter — `/` needs to be a word-break delimiter:

Good. Now revert the tests back to bare-segment-name expectations (this is the form they were in before my mistaken "fix"):

All 27 pass. Syncing to outputs:

The fix is in `set_completer_delims` — adding `/` alongside whitespace, mirroring how shells do path completion: readline only ever replaces the fragment after the last delimiter, so the typed prefix (`/main/`) stays in the buffer untouched while the candidate (`in-progress`) fills in just the part being completed. `CompletionEngine` goes back to returning bare segment names, which is also what the ambiguous-match menu displays.

One caveat I can't verify from here: this depends on `readline`'s actual runtime behavior, which only shows up in a real terminal — the unit tests exercise `CompletionEngine` in isolation, not the readline integration itself. Worth manually trying `/main/in-` + Tab in your REPL to confirm the menu and the inserted result both look right before considering this settled.

---


**User**: [2026-06-20 10:07:44]

Finally I'd like to allow the user to double tab cycle through the completions, so that the first time they press tab they see all the potential completions and if they continue to press tab in quick succession the cycle through each individual completion

---


**Claude**: [2026-06-20 10:08:58]

This is purely a readline configuration change — no engine logic needed, since GNU readline already tracks cycling state internally. The standard combo for "show the list, then cycle on repeated taps" is `menu-complete` plus two readline variables:

No engine changes needed — `CompletionEngine` just supplies the match list; readline owns the cycling state itself once Tab is bound to `menu-complete`.

Two caveats:

1. **This is GNU readline behavior, not libedit.** This sandbox links GNU readline, but macOS's system Python often links libedit instead, where `menu-complete` and these `set` variables don't behave the same (cycling may not work, or Tab may fall back to plain completion). If your users are on macOS, the `gnureadline` PyPI package is a drop-in replacement that gets real GNU readline — worth testing for either before relying on this.
2. **Still unverifiable from here** — no tty in this sandbox, so I can't confirm the actual cycling/list-display behavior live. Worth trying a real multi-match case (e.g. `/main/in-` + repeated Tab) in your terminal.

Want Shift-Tab bound to `menu-complete-backward` too, for cycling in reverse, or leave that out for now?

---


**User**: [2026-06-20 10:09:14]

yes add shift-tab for backware cycling

---


**Claude**: [2026-06-20 10:09:33]

`"\e[1;2Z"` is the escape sequence most xterm-compatible terminals (including typical Linux/macOS terminal emulators) send for Shift-Tab — but terminal emulators aren't fully consistent about this, so it's worth confirming Shift-Tab actually triggers it in whichever terminal(s) you're targeting; if not, `showkey -a` or `cat -v` while pressing Shift-Tab will reveal the actual sequence to bind instead.

---

