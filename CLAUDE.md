# Git Kanban

## Code of Conduct

Keep the user in the loop. Let the user make decisions. Answer prompts with facts, analysis, and recommendations to the best of your ability, but allow the user to determine the path to take.

Prefer asking for more information over nudging the user to a specific course of action. If there are ambiguities work with the user to resolve them before moving on. Let the user tell you when they are ready to scaffold or write code.

Do not praise or patronize. Avoid comments like “great idea” or “good suggestion."

Be succinct.

## Project

We are building a kanban style task manager in python that uses the filesystem for storage and git for change tracking. Tasks are stored as markdown documents in directories that correspond to boards with subdirectories for columns. The task's filename is its title. Metadata is stored as frontmatter in the markdown documents and includes a UUID to uniquely identify a task. A tasks's title (and so filename) may change but its UUID will not. The application uses a caching index for faster searching and for discovering when files have changed on disk outside of the application. The initial interface to the application is a CLI, but we will also support an TUI in the future.

A description of the layered architecture follows. Each layer interacts only with the layer below it.

```
CLI
  ↓
KanbanService (coordinating facade)
  ↓
Domain Services
  ↓
Repositories (ABC)
  ↓
Storage (filesystem + SQLite) / Git
```

**CLI Layer**

- Handles terminal input/output and argument parsing only
- Two consumers of the facade: a plain CLI for scriptable per-invocation commands, and an optional lightweight TUI subcommand (e.g. `kanban ui`)

**Coordinating Facade (KanbanService)**

- Single object called by the CLI
- Orchestrates across domain services, index, and git
- Sequences operations, handles cross-domain validation, manages partial failure
- Only orchestrates — never contains domain logic

**Domain Services**

- One class per domain: `BoardService`, `TaskService`, `SearchService`, `GitService`, `IndexService`
- Return rich domain dataclasses (`Task`, `Board`, `Column`) never formatted strings
- Raise domain exceptions (`TaskNotFound`, `BoardAlreadyExists`) never storage exceptions
- Never touch storage directly — call repository methods only

**Repository Layer**

- Defined as an abstract base class — domain services code against the interface only
- Two concrete implementations: `FilesystemRepository` and `InMemoryRepository` (for testing)
- Concrete implementation injected at startup — domain services never instantiate repositories directly
- Responsible for translating between storage format and domain dataclasses
- Return rich domain dataclasses

**Storage**

- Boards = directories
- Columns = subdirectories
- Tasks = `.md` files
- `pathlib` for all path and file operations
- `shutil` for moves and recursive deletes
- `python-frontmatter` for parsing markdown files into domain dataclasses

**Indexing**

- Start with scan-on-demand (parse markdown on every query)
- Introduce SQLite + FTS5 later as a performance cache once data model is stable
- Index is always a cache — markdown is always the source of truth

**Git**

- Automatic commit per operation with structured messages composed by the facade
- `kanban squash` command to collapse commits before pushing
- Use `pygit2` or `subprocess` — avoid `GitPython`

### Directory Structure

For filesystem storage the directory layout has the following structure in the root project directory:

```
root-directory/
  .kanban/
    config
    index.db
  .kanban-store/
    boards/
      .order
      my-project/
        .order
        todo/
          complete-this-task.md
          also-thistask.md
        in-progress/
        in-review/
        done/
      ops/
        .order
        backlog/
        todo/
        in-progress/
        done/
  project-files/
  ...
```

`.kanban/` contains local machine state (config, cache) that should probably never be committed at all, while  `.kanban-store/` contains the shared board state that git is tracking.

### Git

The kanban store is set up as a git worktree, created when the kanban project is initialized:
 
```
git worktree add .kanban-store kanban
 ```

The kanban-store worktree shares the same object store as the root directory but otherwise has:

- Its own HEAD — tracking which commit it currently has checked out
- Its own index — the staging area for the next commit
- Its own working tree files — the actual files on disk

In order for changes to the kanban-store directory to be tracked in their own worktree, git commands executed by kanban service must be instructed to execute within that folder, for example:

```
git -C .kanban-store push
git -C .kanban-store pull
```

### Metadata

Metadata is stored in markdown frontmatter with the following fields and format:

```
---  
id: a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d
title: Fix login bug
slug: fix-login-bug
created_by: mark
assignee: alice
priority: high
due_date: 2026-06-20
tags: [bug, auth]
created_at: 2026-06-12T10:00:00Z
updated_at: 2026-06-12T10:00:00Z
---  
  
# Descrtion  
  
...
```

### The CLI

The command line structure follows:

```
kanban init
kanban repl [--noun-first]

kanban board list [--format <table|plain|json>] [--sort <title>] [--reverse]
kanban board create <board>
kanban board rename <board> <new-name>
kanban board delete <board>

kanban column list <board> [--format <table|plain|json>] [--sort <title>] [--reverse]
kanban column create <board>/<column>
kanban column rename <board><column> <new-name>
kanban column reorder <board>/<column> <position>
kanban column delete <board>/<column>

kanban task list <board>[/<column>]
    [--format <table|plain|json>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by>]
    [--reverse]
    [--assignee <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban task create <board>/<column>/<title>
    [--assignee <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-date <date>]
    [--created-by <name>]

kanban task update <board>/<column>/<title>
    [--assignee <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-date <date>]
    [--created-by <name>]

kanban task show <board>/<column>/<task> [--format <table|plain|json>]
kanban task edit <board>/<column>/<task>
kanban task move <board>/<column>/<task> <dest>
kanban task delete <board>/<column>/<task>

kanban search <query>
    [--format <table|plain|json>]
    [--board <board>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by>]
    [--reverse]
    [--assignee <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban log <board>/<column>/<task> [--limit <n>]
kanban status [--format <table|plain|json>]

kanban config set <key> <value>    # key: name
kanban config get <key>            # key: name

# Global flags (all commands):
#   --quiet
```

The `[]` brackets indicate optional path components that are inferred from the user context or index search. Path resolution for all commands follows:

1. Explicit path
2. User context
3. Index search (scoped to active board if set)
4. Error on ambiguity

## The REPL

The REPL is the Read-Evaulate-Print-Loop that runs the command line application in an interactive loop. By default the REPL uses a verb first command strcuture but can be started with the `--noun-first` flag to use the same noun first command structure as the non-interactive CLI.

The REPL shares its command parsing and output formatting code with the non-interactive CLI — both call the same KanbanService methods and render the same dataclasses. The only new layer is the read-eval-print loop itself and a few REPL-specific meta-commands:

```
use           - sets the active board/column
help          — list commands
history       — show command history
clear         — clear screen
quit or exit  — exit
```

The REPL prints it prompt as:

```
kanban>
```

### The User Context

The REPL takes advantage of the user contex in the kanban service, allowing the user to set the active board/column. If there is an active board or board/column the REPL shows it in the prompt:

```
kanban (my-project)>
kanban (my-project/todo)>
```

An example REPL interaction follows:

```
$ kanban repl

kanban> use my-project/todo

kanban (my-project/todo)> list tasks
  1. Fix login bug         [high]  alice    due 2026-06-20
  2. Write API docs        [med]   bob      due 2026-06-25

kanban (my-project/todo)> create task "Add rate limiting" --priority high --assignee alice
Created: Add rate limiting [a3f9c2d1]

kanban (my-project/todo)> move task "Add rate limiting" in-progress
Moved to: my-project/in-progress

kanban (my-project/todo)> /history
  task list
  task create "Add rate limiting" --priority high --assignee alice
  task move "Add rate limiting" in-progress

kanban (my-project/todo)> /quit
```

### Tab Completion

The REPL supports tab completion for commands, positional arguments, and paths.

#### For Commands and Positional Arguments

Completion for commands and positional arguments is straightforward and looks like:

```
kanban> m<TAB>
move

kanban> move ta<TABL>
task
```

#### For Paths

Tab completion for board/column/task paths must take into account the user context and the portion of the path so far supplied by the user.

Tab completion is resolved in the following manner:

**When there is no board or column in the user context**

The user must type everything. Completions offer the next segment with a trailing slash to drill in:

```
kanban> move task <TAB>
my-project/   ops/

kanban> move task my-<TAB>
my-project/

kanban> move task my-project/<TAB>
todo/   in-progress/   in-review/   done/

kanban> move task my-project/to<TAB>
todo/

kanban> moave task my-project/todo/<TAB>
fix-login-bug   write-api-docs   add-rate-limiting

kanban> move task my-project/todo/fix<TAB>
fix-login-bug
```

**When there is an board but no column in the user context**

The board segment is skipped. Completion starts at the column, resolved against the active board:

```
kanban (my-project)> move task <TAB>
todo/   in-progress/   in-review/   done/

kanban (my-project)> move task to<TAB>
todo/

kanban (my-project)> move task todo/<TAB>
fix-login-bug   write-api-docs   add-rate-limiting

kanban (my-project)> move task todo/fix<TAB>
fix-login-bug
```

**When there is a board and column in the user context**

Both segments are skipped. Completion starts directly at the task title:

```
kanban (my-project/todo)> move task <TAB>
fix-login-bug   write-api-docs   add-rate-limiting

kanban (my-project/todo)> move task fix<TAB>
fix-login-bug
```

**In the the mixed case when the user overrides the context with an explicit path**

The completer detects that board (and column) are being supplied explicitly and resolves subsequent segments from what's been typed rather than from context:

```
# Active context is my-project/todo, but user is typing a path from ops/
kanban (my-project/todo)> move task ops/<TAB>
backlog/   todo/   in-progress/   done/

kanban (my-project/todo)> move task ops/in-pro<TAB>
in-progress/

kanban (my-project/todo)> move task ops/in-progress/<TAB>
deploy-staging   update-certs   rotate-keys

# Active context is my-project, user supplies board and column explicitly
kanban (my-project)> move task ops/todo/<TAB>
deploy-staging   update-certs   rotate-keys
```

The signal that the user is overriding the context is simply the presence of a `/` in the typed text. One slash means they've supplied a board; two slashes means they've supplied both a board and column. 

## Additional Instructions

- Use python as the programming language
- The name of the root python package is `kanban`
- When writing python prefer dot notation to `getattr`, especially when the type is known
- Explicity type object arguments to parameters
- When a python dependency is required add it to the pyproject files
- Add documenation when you create types and methods, including for tests
- When you make changes to CLI subcommands, update the the command line structure in CLAUDE.md if necessary
- When you make changes to REPL commands, update the REPL structure if necessary
