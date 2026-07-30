# Git Kanban

## Code of Conduct

Keep the user in the loop. Let the user make decisions. Answer prompts with facts, analysis, and recommendations to the best of your ability, but allow the user to determine the path to take.

Prefer asking for more information over nudging the user to a specific course of action. If there are ambiguities work with the user to resolve them before moving on. Let the user tell you when they are ready to scaffold or write code.

Do not praise or patronize. Avoid comments like “great idea” or “good suggestion."

Be succinct.

## Python

- Use python as the programming language
- The name of the root python package is `kanban`
- Use dot notation instead of `getattr`, especially when the type is known
- Prefer explicit types over `object` and add type whenever possible
- Use double quotes `"..."` for strings
- When typing optionals prefer `typ | None` instead of `Optional(typ)`
- When a python dependency is required add it to pyproject.toml
- Add documentation when creating types and methods, including for tests
- Break up tests, keep unit tests small
- Run tests from the current working directory with the bash command `python -m unittest discover -s tests`
- Tab indent key-value pairs in INI files

## Documentation

- When you make changes to CLI subcommands, update the the command line structure in CLAUDE.md if necessary
- When you make changes to REPL commands, update the REPL structure if necessary

## Project

We are building a kanban style task manager in python that uses the filesystem for storage and git for change tracking. Tasks are stored as markdown documents in directories that correspond to boards with subdirectories for columns. The task's filename is the slug conversion of its title.

Metadata is stored as frontmatter in the markdown documents and includes a UUID to uniquely identify a task. A tasks's title (and so filename) may change but its UUID will not. The application uses a caching index for faster searching and for discovering when files have changed on disk outside of the application. The initial interface to the application is a CLI, but we also have a REPL and a TUI.

The filesystem is the source of truth

You could just use the shell and your text editor of choice, but we’re adding metadata, automatic commits, an index for fast searching, a REPL, and a TUI.

A description of the architecture follows. Each layer interacts only with the layer below it.

```
CLI | REPL | TUI
  ↓
Kanban Service (coordinating facade)
  ↓      ↓
  ↓   Domain Services
  ↓      ↓
Repositories (ABC)
  ↓
Storage (filesystem + SQLite) / Git
```

An individual layer can be broken down into more detail. For example the CLI looks like:

```
Parser
  ↓
Command Handler 
  ↓      ↓
  ↓   Renderer
  ↓      ↓
  ↓   Render Helper
  ↓      ↓  
Kanban Service
```

Once again each layer only interacts with the layers below it.

### The Filesystem is the Source of Truth

The filesystem is the single source of truth. Layers do not cache results from the layer below them. Data model objects do not have access to the objects they contain or which contain them. Every time the `KanbanService` needs data from a domain service or the respository, it asks for it. Every time a repository needs data from storage, it asks for it, which means querying the filesystem.

The index does cache data from the filesystem for search and to ensure consistency (was the kanban store changed outside the application). It is updated by the `KanbanService` after every write to the repository.

### Overall Architecture

**CLI Layer**

- Handles terminal input/output and argument parsing only
- Three consumers of the coordinating facade: 
- A plain CLI for scriptable per-invocation commands
- A REPL for interactive commands in a loop (e.g. `kanban repl`)
- A lightweight TUI (e.g. `kanban tui`)

**Coordinating Facade (KanbanService)**

- Single object called by the CLI/REPL/TUI
- Orchestrates across domain services, storage, the index, and git
- Sequences operations, handles cross-domain validation, manages partial failure
- Only orchestrates — never contains domain logic
- Raises exceptions if conditions required to call into domain services or repository layer are missing

**Domain Services**

- One class per domain: `BoardService`, `TaskService`, `SearchService`, `GitService`, `IndexService`. 
- In practice the datamodel services are handled by the `KanbanService`.
- Return rich domain dataclasses (`Task`, `Board`, `Column`) never formatted strings
- Raise domain exceptions (`TaskNotFound`, `BoardAlreadyExists`) never storage exceptions
- Never touch storage directly — call repository methods only

**Repository Layer**

- Defined as an abstract base class — domain services code against the interface only
- Two concrete implementations: `FilesystemRepository` and `InMemoryRepository` (for testing)
- Concrete implementation injected at startup — domain services never instantiate repositories directly
- Responsible for translating between storage format and domain dataclasses
- The `Repository` is the source of truth for the `KanbanService.`
- Return rich domain dataclasses

**Storage**

- Boards = directories
- Columns = subdirectories
- Tasks = `.md` files
- `pathlib` for all path and file operations
- `shutil` for moves and recursive deletes
- `python-frontmatter` for parsing markdown files into domain dataclasses. In practice frontmatter is parsed manually.

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
root-directory
├── .kanban
│   ├── config
│   ├── history
│   └── index.db
│   └── userdata
├── .kanban-store
│   └── boards
│       ├── .metadata
│       ├── main
│       │   ├── .metadata
│       │   ├── todo
│       │   │   └── .metadata
│       │   │   └── complete-this-task.md
│       │   │   └── and-this-task.md
│       │   ├── in-progress
│       │   │   └── .metadata.metadata
│       │   ├── in-review
│       │   │   └── .metadata.metadata
│       │   └── done
│       │       └── .metadata.metadata
│       └── another-board
│           ...
└── project-files
    ...
```

`.kanban/` contains local machine state (config, cache) that should not be commited to git, while  `.kanban-store/` contains the shared board state that git is tracking. Information about boards and columns that is not stored in the files themselves, such as their original names and sort order, is kept in a `.metadata` INI file local to each folder.

### Git

The kanban store is set up as a git worktree, created when the kanban project is initialized and before the kanban store folder is created. It must be created in multiple steps using an orphan branch.
 
```bash
# 1. create the orphan branch (must be done from the main working tree)
git checkout --orphan kanban

# clear inherited working tree files
git rm -rf .
git commit --allow-empty -m "kanban: initialize"

# return to main branch
git checkout main

# 2. now add the worktree pointing at the orphan branch
git worktree add .kanban-store kanban
```

A cleaner approach creates the orphan branch without touching the main working tree:

```bash
# create an empty tree object
EMPTY_TREE=$(git hash-object -wt tree /dev/null)

# create a commit with no parents pointing at the empty tree
INIT_COMMIT=$(echo "kanban: initialize" | git commit-tree $EMPTY_TREE)

# create the branch ref pointing at that commit
git update-ref refs/heads/kanban $INIT_COMMIT

# now add the worktree
git worktree add .kanban-store kanban
```

The kanban-store worktree shares the same object store as the root directory but otherwise has:

- Its own HEAD — tracking which commit it currently has checked out
- Its own index — the staging area for the next commit
- Its own working tree files — the actual files on disk

In order for changes to the kanban-store directory to be tracked in their own worktree, git commands executed by kanban service must be instructed to execute within that folder, for example:

```bash
git -C .kanban-store push --set-upstream origin kanban

git -C .kanban-store add boards/my-project/todo/fix-login-bug.md
git -C .kanban-store commit -m "kanban: task created"
git -C .kanban-store status

git -C .kanban-store push
git -C .kanban-store pull
```

The worktree and branch are stored in the .kanban/config file:

```INI
[repository]
  worktree = ".kanban-store"
  branch = "kanban"
```

### The Data Model

There are three core types: the board, column, and task. A board contains columns, and a column contains tasks. A task belongs to a single column; a column belongs to a single board.

#### Identity

There are three ways of identifying a board, column, or task: by id, path, or slug.

The `id` is the unique identifier. It is the only identifier that is immutable. The id is created when the object is created. It is used when checking for changes made directly to the filesystem outside of the kanban application.

The `slug` is derived from the object's name. The name is is the display name given to the object by the user. The name maybe changed, in which case the slug also changes.

The slug identifies the associated file or folder on disk and is used to construct filepaths. It is unique in its context. Slugging is owned by the service layer, and a slug is only created or updated when the object is created or updated. No other layer creates slugs, but consumers of the kanban service may provide a custom slug when creating or updating an object. Repository methods take slugs as parameters but do not create slugs themselves.

The REPL and TUI use the slug to identify an object when making calls to the service layer. Because of its importance the slug is typed:

```
Slug = NewType('Slug', str)
```

The `path` is an object's fully qualified path and is globally unique. It is composed of slugs and changes when an object's slug changes.

```
/board/column/task
```

For example:

`/main` identifies the Main board

`/main/todo` identifies the To Do column in the Main board

`/main/todo/fix-bug` identifies the "Fix Bug" task in the To Do column of the Main board

Paths correspond directly to files and folders when using the filesystem repository. Other repositories use the path as a unique identifer in whatever way appropriate.

The CLI uses the path to identify an object when making calls to the service layer. Because of this most `KanbanService` methods take identifying arguents that are typed `Path | Slug`.

The data model follows. Note the lightweight relationships between the types.

#### The Board

```python
@dataclass
class Board:
    id:   UUID
    name: str
    slug: Slug

    column_count: int = 0
    task_count: int = 0
```

#### The Column

```python
@dataclass
class Column:
    id:         UUID
    name:       str
    slug:       Slug
    board:      Slug
    position:   int

    task_count: int = 0
```

#### The Task

```python
@dataclass
class Task:
    id:             UUID
    title:          str
    slug:           Slug
    board:          Slug
    column:         Slug

    created_by:     str | None = None
    assigned_to:    str | None = None
    priority:       Priority | None = None
    due_date:       datetime | None = None
    tags:           list[str] = field(default_factory=list)
    created_at:     datetime | None = None
    updated_at:     datetime | None = None
    body:           str = ""
```

### Metadata

#### The Store

The kanban store includes a `userdata` INI file. It contains preferences specific to the user and is added to the git ignore. (TODO) For example the user's most recently active /board/column is saved here and reloaded when the user starts the repl. For example:

```
[user-context]
    board = main
```

#### Boards

There is no intraboard metadata at this time. Boards are sorted alphabetically.

#### Board

Board (singular) metadata is stored in a hidden `.metadata` extendend INI file in each board directory. It contains settings that apply to the board, for example its name, slug, and the column order:

```
[columns]
    order =
        todo
        in-progress
        in-review
        done

[fields]
  name="Main"
  slug="main"
```

#### Column

Columns metadata is stored in a hidden `.metadata` INI file in each column's directory. It contains settings that apply to the column, for example its name, slug, and the task order:

```
[tasks]
    order =
        finish-git-kanban
        go-for-a-bike-ride
        have-a-cup-of-tea

[fields]
    name="To Do"
    slug="todo"
```

#### Task

Task metadata is stored in the task's markdown file as frontmatter with the following fields and format:

```
---  
id: a3f9c2d1-8b4e-4f2a-9c1d-3e7f8a2b5c6d
title: Fix login bug
slug: fix-login-bug
created_by: mark
assigned_to: alice
priority: high
due_date: 2026-06-20
tags: [bug, auth]
created_at: 2026-06-12T10:00:00Z
updated_at: 2026-06-12T10:00:00Z
---  
# Description  
...
# Comments
...
```

Following the frontmatter are two sections delineated by markdown headers: the task's Description and Comments that have been added to the task. The `# Description` header is added to the task's markdown when it is created. The `# Comments` header is added only when a comment has been made on the task.

### The CLI

The command line structure follows:

```
kanban init
kanban repl
kanban tui

kanban board list
kanban board create <board>
kanban board info <board>
kanban board rename <board> <new-name>
kanban board delete <board>

kanban column list <board>
kanban column create <board> <column>
kanban column info <board>/<column>
kanban column rename <board>/<column> <new-name>
kanban column reorder <board>/<column> <position>
kanban column delete <board>/<column>

kanban task list <board>[/<column>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by|<column>]
    [--reverse]
    [--exclude <column>]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban task create <board>/<column> <title>
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-date <date>]
    [--created-by <name>]
    [--description <text>]

kanban task update <board>/<column>/<task>
    [--column <column>]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-date <date>]
    [--created-by <name>]
    [--description <text>]

kanban task unset <board>/<column>/<task>
    [--assigned-to]
    [--priority]
    [--tag <tag>]
    [--due-date]
    [--created-by]
    [--description]

kanban task move <board>/<column>/<task>
    [<column>]
    [--top]
    [--bottom]
    [--up]
    [--down]

kanban task info <board>/<column>/<task>
kanban task view <board>/<column>/<task>
    [--markdown]

kanban task edit <board>/<column>/<task>
kanban task delete <board>/<column>/<task>
kanban task assign <board>/<column>/<task> (<name> | --remove)
kanban task tag <board>/<column>/<task> <tag>
    [--remove]
kanban task comment <board>/<column>/<task> (<comment> | --edit)
kanban task rename <board><column>/task <new-name>

kanban search <query>
    [--board <board>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by>|<column>]
    [--reverse]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban log <board>/<column>/<task> [--limit <n>]
kanban status

kanban config set <key> <value>    # key: name
kanban config get <key>            # key: name
```

Most commands take a `--format` argument with options `plain|json` (default: `plain`).

### Object Paths

Objects are identified by their absolute path consisting of `/board/column/task` components as available.

When creating or updating an object the CLI slugs its title to produce a path component. The full path is always printed to the console and is used to identify the object in future calls to the CLI.
Absolute paths are implied by the CLI. When executing a command the CLI adds a forward slash to any identifying path that does not begin with one.

For example:

```
$ kanban board list
/main

$ kanban colum list /main
/todo
/in-progress
/in-review
/done

$ kanban task create /main/todo "Ensure the CLI outputs paths"
/main/todo/ensure-the-cli-outputs-paths
```

## The REPL

The REPL is the Read-Evaulate-Print-Loop that runs the command line application in an interactive loop. The REPL uses a verb first command structure.

The REPL sits at the same level in the architecture as the CLI and it consumes the same KanbanService. It has a dedicated renderer, and it adds a user context which keeps track of the active board, modeled as the current working directory. If a command takes a path argument and it does not begin with a forward slash, the command is executed within the context of the active board.

The REPL command structure follows:

```
init [-b|--bootstrap]

board <board>

boards [--slugs]
columns [--slugs]

tasks [<column>]
    [--slugs]
    [--exclude <column>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by|column>]
    [--reverse]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

create <column> <title> | --column <name> | --board <name>
    [--edit]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-date <date>]
    [--created-by <name>]
    [--description <text>]

rename <task> | --column <column> | --board <new-name>
delete <task> | --column <column> | --board
    [--force]

view <task> [-p|--plain]
info <task>
edit <task>

update <task>
    [--column <column>]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-date <date>]
    [--created-by <name>]
    [--description <text>]

unset <task>
    [--assigned-to]
    [--priority]
    [--tag <tag>]
    [--due-date]
    [--created-by]
    [--description]

move <task> [<column>]
    [--top]
    [--bottom]
    [--up]
    [--down]

comment <task> (<comment> | --edit)
assign <task> (<user> | --remove)
tag <task> <tag>
    [--remove]

reorder <column> <position>

config
config set <key> <value>    # key: name
config get <key>            # key: name

search <query>
    [--slugs]
    [--board <board>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by|column>]
    [--reverse]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

log [</board|[/board/]column|[/board/]column/task>] [--limit <n>]

status

exit

# Every subcommand also accepts -h/--help.
# No global flags are currently active for the REPL (see _add_global_flags).
```

The `[]` brackets indicate optional path components that are inferred from the user context or index search. Path resolution for all commands follows:

1. Explicit path
2. User context
3. Index search (scoped to active board if set)
4. Error on ambiguity

Task-target commands (`show`, `edit`, `update`, `move`, `assign`, `rename`, `delete`) identify a task by its bare `<task>` slug: the service locates the column that contains it within the active board and constructs the full path. Because slugs are unique board-wide, the column need not be given. To target a column or the active board, `rename` and `delete` use the `--column <column>` and `---board` flags respectively.

The following command aliases are registered by default:

```
 new = create
   n = create
cols = columns
  mv = move
 del = delete
  rm = delete
show = view
   v = view
   s = view
   i = info
quit = exit
  :q = exit
```

The REPL supports control commands and tab completion:

```
Ctrl+C        - interrupt or cancel the current command
Ctrl+L        - clear the screen
Ctrl+D        - exit
Ctrl+Z        - exit
Tab           - context aware automcomplete commands, flags, files, tags, users, tags, etc
```

The REPL prints it prompt as:

```
kanban (/board) >
```

### The User Context

The user context is a service level model of user settings and preferences. It includes for example the active board. The REPL takes advantage of the user contex in the kanban service. If there is an active board the REPL shows it in the prompt:

```
kanban (/my-project) >
```

An example REPL interaction follows:

```
$ kanban repl

kanban () > board my-project

kanban (/my-project)> tasks todo
  1. Fix login bug         [high]  alice    due 2026-06-20
  2. Write API docs        [med]   bob      due 2026-06-25

kanban (/my-project)> new todo "Add rate limiting" --priority high --assigned-to alice
Created: Add rate limiting [a3f9c2d1]

kanban (/my-project)> mv add-rate-limiting in-progress
Moved to: in-progress

kanban (/my-project)> history
  task list
  task create "Add rate limiting" --priority high --assigned-to alice
  task move "Add rate limiting" in-progress

kanban (/my-project)> quit
```

### Tab Completion

The REPL supports tab completion for commands, positional arguments, and paths.

#### For Commands and Positional Arguments

Completion for commands, positional and optional arguments is straightforward. If there is only one option available it is autocompleted with a tab.

```
kanban (/my-project) > mo<TAB>
kanban (/my-project) > move

kanban (/my-project) > new to<TAB>
kanban (/my-project) > new todo

kanban (/my-project) > new todo --pri<TAB>
kanban (/my-project) > new todo --priority
```

If there is more than one option tabbing quickly in succession cycles through them:

```
kanban (/my-project) > m<TAB>
move     mv     <TAB>
kanban (/my-project) > move<TAB>
kanban (/my-project) > mv<TAB>
kanban (/my-project) > m
```

#### For Slugs

Tab completion for board, column, and task slugs works as expected. Positional and optional arguments are identified by the command parser as board, column, or task arguments, and tab completion completes the slugs that are avaialble for the type:

```
kanban (/my-project) > move fix<TAB>
fix-login-bug   fix-rename-output   fix-repl-init

kanban (/my-project) > rename --column in<TAB>
in-progress     in-review

kanban (/my-project) > tasks to<TAB>
kanban (/my-project) > tasks todo
```

As with commands and other argumenbts, if there is more than one option for a slug previx tabbing quickly in succession cycles through them.

## The TUI

The Text User Interface (TUI) provides a visual but still text based user interface to the underlying kanban service. Kanban means "signboard" or "visual card" in Japanese, so providing a visual, card based system is a requisite part of this application.

The TUI is entirely keyboard driven with the following input properties:

- **Navigation** — Arrow keys or vim-style `h/j/k/l` move focus between columns and cards. `Tab` cycles between columns.

- **Actions on the selected card** — single-key commands trigger instantly: `m` to move a card to another column, `e` to open an edit panel, `d` to delete (with a confirmation prompt), `Enter` to expand card details.

- **Command palette** — The addition of a `/` or `:` prompt for power users to type commands like `:move 14 done` or `:assign 11 sara`.

- **Search/filter** — `/` or `f` opens an inline search bar that live-filters visible cards as you type.

The TUI has the following output properties and formatting conventions:

- **Box-drawing characters** (`┌ ─ ┐ │ └ ┘ ├ ┤`) form the card and column borders, giving a structured grid feel without a GUI.

- **Color carries semantic meaning** — red for critical priority, yellow for high, green for done, dim/grey for archived items. Active focus gets a highlighted border or inverted colors.

- **Density toggles** — a keypress like `c` might collapse cards to single-line summaries when you have many, expanding them on focus.

- **Status bar at the bottom** always shows contextual key hints for the current mode, so the user is never guessing what's available.

- **Inline metadata** uses compact sigils: `!HIGH` for priority, `@name` for assigned to, `#id` for card number, so cards stay readable at a glance without taking up too much vertical space.

We will be using the `textual` python library to build the TUI

### The Visual Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  🗂  My Kanban Board                          [?] Help  [q] Quit │
├──────────────────┬──────────────────┬──────────────────┬────────┤
│    BACKLOG (4)   │  IN PROGRESS (2) │   REVIEW (1)     │DONE(8) │
│                  │                  │                  │        │
│ ┌──────────────┐ │ ┌──────────────┐ │ ┌──────────────┐ │ ✓ #12  │
│ │ #14 Fix nav  │ │ │▶ #11 Auth    │ │ │ #09 API docs │ │ ✓ #11  │
│ │ !HIGH  @sara │ │ │   flow       │ │ │ !MED  @alex  │ │ ✓ #10  │
│ │ 3d estimate  │ │ │ !HIGH @tom   │ │ └──────────────┘ │  ...   │
│ └──────────────┘ │ │ due: Jun 15  │ │                  │        │
│                  │ └──────────────┘ │                  │        │
│ ┌──────────────┐ │                  │                  │        │
│ │ #13 Dark mode│ │ ┌──────────────┐ │                  │        │
│ │ !LOW  @alex  │ │ │▶ #08 Payment │ │                  │        │
│ └──────────────┘ │ │   refactor   │ │                  │        │
│                  │ │ !CRIT @sara  │ │                  │        │
└──────────────────┴──────────────────┴──────────────────┴────────┘
  ←/→ columns   ↑/↓ cards   [m] move   [n] new   [e] edit   [d] del
```

### The Application Structure

```
KanbanApp(App)
│
├── BoardScreen (default screen)
│   ├── Header (board name, active column count)
│   │
│   ├── Horizontal
│   │   ├── ColumnView(ListView) × N        — main board area
│   │   │   └── CardWidget(Static) × N      — one per task in that column
│   │   │       states: default | focused | move-mode (dashed amber border)
│   │   │
│   │   └── SidebarPanel (collapsible, right side)
│   │       ├── StatusView                  — renders KanbanService.status()
│   │       └── LogView                     — renders git log, scoped to
│   │                                          focused task or board if none
│   │
│   └── Footer (key bindings hint bar — swaps content in move mode)
│
├── TaskDetailScreen (modal, pushed on Enter/show)
│   └── renders a single Task: title, assigned_to, priority, due date, tags, description, comments
│
├── TaskFormScreen (modal, pushed on create/edit)
│   ├── Input: title
│   ├── Input: assigned_to
│   ├── Select: priority
│   ├── Input: due date
│   ├── Input: tags (comma separated)
│   └── Button row: Save / Cancel
│
├── BoardSwitcherScreen (modal, pushed on `b`)
│   └── ListView of board names — Enter switches BoardScreen's active board
│       plus a "+ New board…" row that pushes BoardFormScreen
│
├── BoardFormScreen (modal, pushed from the board switcher)
│   ├── Input: title
│   └── Button row: Save / Cancel
│       on save BoardScreen creates the board and switches to it
│
└── CommandBar (overlay, toggled by `:`)
    └── Input — free text, parsed with the same parser as the REPL
```

#### Key Bindings (Board Screen, normal mode)

```
←/→ or h/l     move focus between columns
↑/↓ or j/k     move focus between cards within a column
Enter          open TaskDetailScreen for focused card
n              open TaskFormScreen (create)
e              open TaskFormScreen (edit, pre-filled)
d              delete focused card (confirm modal)
m              enter move mode for focused card
b              open BoardSwitcherScreen
/              inline filter — live-filters visible cards as typed
:              open CommandBar — full REPL-syntax command line
s              toggle SidebarPanel collapse
q / Ctrl+Q     quit
?              help screen — bindings reference
```

#### Key bindings (move mode, once `m` pressed)

```
←/→ or h/l     move card to adjacent column
↑/↓ or j/k     reorder card within current column
Enter          commit — single move_task/reorder call
Esc            cancel — discard, no calls made
```

### Refresh Strategy

The filesystem remains the source of truth for the TUI, and the TUI consumes the kanban service exclusively, which itself queries the filesystem, no different from the CLI or REPL, but because the TUI maintains a visual state in a running application while the filesystem might change, it becomes necessary to develop a data refresh strategy. Our approach is threefold:

1) **After own mutations** — every create/edit/move/delete re-fetches from KanbanService immediately, so the TUI never shows stale data caused by its own actions.

2) **On terminal focus return** — when the app detects the terminal window regained focus (via terminal focus-reporting escape sequences, exposed through Textual's app-level focus/blur events), it re-syncs from the filesystem. This catches the common case of switching away to run git pull or edit a file, then switching back.

3) **Manual refresh key** (`r` or `:refresh`) — explicit fallback for when focus-tracking isn't supported (notably gaps in tmux/screen pass-through) or when something changes while the terminal stays focused the whole time.

In addition the TUI will refresh whenever a git sync is executed from within the app, akin to refreshing after a mutation.
