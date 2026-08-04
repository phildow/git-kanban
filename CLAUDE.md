# Git Kanban

## Code of Conduct

Keep the user in the loop. Let the user make decisions. Answer prompts with facts, analysis, and recommendations to the best of your ability, but allow the user to determine the path to take.

Prefer asking for more information over nudging the user to a specific course of action. If there are ambiguities work with the user to resolve them before moving on. Let the user tell you when they are ready to scaffold or write code.

Do not praise or patronize. Avoid comments like “great idea” or “good suggestion."

Be succinct.

## Documentation

Update CLAUDE.md when making structural or system design changes. Be even more succinct. CLAUDE.md is a README for humans and machines. Reserve updates to CLAUDE.md for structural changes. Do not include implementation details.

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
- Run tests from the current working directory with the bash command `python -m pytest -n auto`
- Tab indent key-value pairs in INI files

## Project

We are building a kanban style task manager in python that uses the filesystem for storage and git for change tracking. Tasks are stored as markdown documents in directories that correspond to boards with subdirectories for columns. The task's filename is the slug conversion of its title.

Metadata is stored as frontmatter in the markdown documents and includes a UUID to uniquely identify a task. A tasks's title (and so filename) may change but its UUID will not. The application uses a caching index for faster searching and for discovering when files have changed on disk outside of the application. The initial interface to the application is a CLI, but we also have a REPL and a TUI.

The filesystem is the source of truth.

You could just use the shell and your text editor of choice, but we’re adding metadata, automatic commits, an index for fast searching, a REPL, and a TUI.

A broad outline of the architecture follows. Each layer interacts only with the layer below it.

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

**Interaction**

- How anything below the consumer layer asks the user a question: a confirmation, or an edit
- An abstract base class injected into the `KanbanService` at startup, like every other service
- `TerminalInteraction` prompts and launches `$EDITOR`; the CLI and REPL use it, and it is the default
- The TUI installs a `DeferredInteraction` instead, which raises `InteractionRequired` — the board puts the question up as a modal and runs the command again with the answer
- A command therefore abandons whatever it was doing at the point it asked, so nothing may be written before a question
- Nothing below the consumer layer reads stdin or launches a program by any other route

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
│   ├── tui-history
│   ├── tui-filter-history
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

#### Setting up a Worktree
 
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

#### Using the Worktree

In order for changes to the kanban-store directory to be tracked in their own worktree, git commands executed by kanban service must be instructed to execute within that folder, for example:

```bash
git -C .kanban-store push --set-upstream origin kanban

git -C .kanban-store add boards/my-project/todo/fix-login-bug.md
git -C .kanban-store commit -m "kanban: task created"
git -C .kanban-store status

git -C .kanban-store push
git -C .kanban-store pull
```

#### Onboarding a New Team Member

When setting up a new teammate with the kanban store after cloning the repository, you must run the following commands:

```bash
git checkout kanban
git checkout main
git worktree add .kanban-store kanban
```

In python:

```python
def init(repo_path):
    repo = pygit2.Repository(repo_path)
    
    if "origin/kanban" in repo.branches.remote:
        # branch exists on remote — check it out into the worktree
        repo.create_branch("kanban", repo.branches.remote["origin/kanban"].peel())
        subprocess.run(["git", "worktree", "add", ".kanban-store", "kanban"])
    else:
        # first time — create the orphan branch and push it
        _create_orphan_branch(repo)
        subprocess.run(["git", "worktree", "add", ".kanban-store", "kanban"])
        subprocess.run(["git", "-C", ".kanban-store", "push", "--set-upstream", "origin", "kanban"])
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

The `slug` is derived from the object's name. The name is is the display name given to the object by the user. The name may changed, in which case the slug changes.

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

    deleted: bool = False
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
    role:       str | None = None

    deleted:    bool = False
```

`role` marks a column the application treats specially rather than as a step in the workflow. Only `archive` is defined. It is assigned when the column is created and survives a rename, so the archive is always found by role, never by slug.

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

    deleted:        bool = False
```

`deleted` is never read from storage. The service sets it on the record it returns from a delete, so a renderer handed that record can tell it apart from a live one.

### The Archive

Every board ends with an archive column, created with the board and marked `role = archive`. Archiving a task is moving it into that column and unarchiving it is moving it back out; nothing is written on the task itself, so where it sits is the whole of it. When it was archived will come from the git history later. A board created before archiving existed gets its archive column the first time something is archived on it.

Archived tasks are left out of listings and out of search. The `--include-archived` flag includes them. Naming the archive column lists them too — a column named is a column returned. An error is raised if a command has both `--include-archived --exclude <archive>`.

The CLI and REPL treat the archive as one more column. The TUI leaves it off the board until `A` asks for it.

### Metadata

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
[fields]
    name="To Do"
    slug="todo"

[tasks]
    order =
        finish-git-kanban
        go-for-a-bike-ride
        have-a-cup-of-tea
```

The archive column carries a `role` field alongside them:

```
[fields]
    name="Archive"
    slug="archive"
    role="archive"
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

## 2026-06-12 @mark

Investigating.

## 2026-06-13 @alice

Fixed on the auth branch.
```

Following the frontmatter are two sections delineated by markdown headers: the task's Description and Comments that have been added to the task. The `# Description` header is added to the task's markdown when it is created. The `# Comments` header is added only when a comment has been made on the task.

Each comment is filed under an `## H2` heading of its own carrying the date it was made, in `YYYY-MM-DD` format, and — when the `user.name` config value is set — the author as `@name`. Comments are only ever appended, never rewritten.

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
    [--include-archived]
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
    [--exclude <column>]
    [--include-archived]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban log <board>/<column>/<task> [--limit <n>]
kanban status

kanban config set <key> <value>
kanban config get <key>
kanban config list
```

Most commands take a `--format` argument with options `plain|json` (default: `plain`).

Note the following default behaviors:

```
kanban task list <board>  # does not include archived tasks
kanban search <query>     # does not include archived tasks
```

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
    [--include-archived]
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
config set <key> <value>
config get <key>

search <query>
    [--slugs]
    [--board <board>]
    [--exclude <column>]
    [--include-archived]
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
   Tab = context aware automcomplete commands, flags, files, tags, users, tags, etc
Ctrl+C = interrupt or cancel the current command
Ctrl+L = clear the screen
Ctrl+D = exit
Ctrl+Z = exit
```

The REPL prints it prompt as:

```
kanban (/board) >
```

### The User Context

The user context is a service level model of user settings and preferences. It includes for example the active board, and it is persisted to userdata. The REPL takes advantage of the user contex in the kanban service. If there is an active board the REPL shows it in the prompt:

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

### The Selection

Beside the user context the service holds a `Selection` — the board, column, and task a consumer has selected on screen. Only a consumer with a cursor sets it, which is the TUI; the CLI runs once and the REPL has a prompt, so there it stands empty and every command behaves as it always has.

It is live screen state, not a setting: held for the session, never written to userdata, and cleared whenever the board screen rebuilds. It may name a task the store no longer holds, so a command resolves it and carries on without it when it does not resolve — a selection is a convenience, never a requirement. `create` is the first command to use one: `new-task.insert` set to `above` or `below` places the new task against `selection.task`.

The board screen syncs the selection on every card highlight and every focus change, but only while a column of its own holds the focus. Focus moving to the command bar or a modal leaves the last selection standing, which is the card the user was on when they started typing and the one a command from the bar is meant for.

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

- **Actions on the selected card** — single-key commands trigger instantly: `m` to move a card to another column, `e` to open an edit panel, `d` to delete (with a confirmation prompt), `a` to archive (likewise), `Enter` to expand card details.

- **Command palette** — The addition of a `/` prompt for power users to type commands like `/move 14 done` or `/assign 11 sara`.

- **Search/filter** — `:` opens an inline search bar that live-filters visible cards as you type.

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
│   │   ├── ColumnPanel(Vertical) × N       — main board area; carries the
│   │   │   │                                 column's border and focus colours
│   │   │   ├── ColumnHeader(Vertical)      — focusable strip: name and count,
│   │   │   │                                 or the field a column is named in
│   │   │   └── ColumnView(ListView)        — the cards, a focus target of its own
│   │   │       └── CardWidget(Static) × N  — one per task in that column
│   │   │           states: default | focused | move-mode (dashed amber border)
│   │   │
│   │   └── SidebarPanel (collapsible, right side)
│   │       ├── StatusView                  — renders KanbanService.status()
│   │       └── LogView                     — renders git log, scoped to
│   │                                          focused task or board if none
│   │
│   └── Footer (key bindings hint bar — swaps content in move mode)
│
├── TaskDetailScreen (modal, pushed on Enter/show)
│   ├── renders a single Task: title, assigned_to, priority, due date, tags, description, comments
│   └── the board's ←/→ ↑/↓ and h/j/k/l keep moving the selection underneath and
│       the screen redraws on the task they land on.
│
├── TaskFormScreen (modal, pushed on create/edit)
│   ├── Input: title
│   ├── Input: assigned_to
│   ├── Select: priority
│   ├── Input: due date
│   ├── Input: tags (comma separated)
│   └── Button row: Save / Cancel
│
├── BoardSwitcherScreen (modal, pushed on `b`, and on startup when no board is active)
│   ├── PrefixList of board names — typing jumps to a board by slug, Enter
│   │   switches BoardScreen's active board; plus a "+ New board…" row
│   ├── Input — a board named in place, laid over the row it belongs to on a
│   │   layer of its own (an OptionList draws its rows, it cannot mount one)
│   └── Static — the key hints, swapped for the field's while naming
│       `N` appends a row and names a new board in it, as "+ New board…" does;
│       `R` renames the highlighted board on its row; `D` deletes it after a
│       ConfirmScreen.
│
├── ConfigScreen (modal, pushed from the command palette's "Configuration")
│   └── PrefixList of KanbanService.list_config() — every supported keypath and
│       its value, unset keys included, grouped under a heading per keypath
│       section; typing jumps to a name, Enter or `e` pushes ConfigValueScreen
│
├── ConfigValueScreen (modal, pushed from the configuration screen)
│   ├── Input: value (pre-filled with the current one)
│   └── Button row: Save / Cancel
│       on save ConfigScreen writes it with set_config and redraws the row
│
└── CommandBar (overlay, toggled by `/`)
    ├── Input — free text, parsed with the same parser as the REPL, and run
    │   against the service's Selection, which the bar taking focus leaves
    │   standing on the card the user was on.  Running a command leaves the bar
    │   open and focused for the next one; Esc closes it and the panel with it.
    │   A command that asks the user something asks it here: a confirmation
    │   opens ConfirmScreen and re-runs on the answer, an edit opens
    │   TaskFormScreen — see Interaction
    └── OutputPanel — what the last command printed, docked directly above the
        bar, scrolling in both directions and never narrower than 80 columns.
        ⇧⇥ moves the focus between the bar and the panel, and nowhere else
        while the bar is open; the panel takes the board's keys while it has
        the focus, so scrolling never reaches a card
```

#### The Command Palette

The palette (`ctrl+p`) carries app-level actions, the ones with no key of their
own. **Configuration** opens `ConfigScreen`; **Theme** opens `ThemePalette`.

#### Key Bindings (Board Screen, normal mode)

```
←/→ or h/l = move focus between columns
↑/↓ or j/k = move focus between cards within a column
         c = focus the header of the column in focus
       Tab = step through the columns — headers are skipped
     Enter = open TaskDetailScreen for focused card
         n = open TaskFormScreen (create)
         e = open TaskFormScreen (edit, pre-filled)
         d = delete focused card (confirm modal)
         m = enter move mode for focused card
         a = archive focused card, or bring it back (confirm modal)
         A = show or hide the archive column — hidden every session
         b = open BoardSwitcherScreen
         / = open CommandBar — full REPL-syntax command line
         : = inline filter — live-filters visible cards as typed; ↵ hands the
             focus back to the board and leaves the bar up, coloured, while the
             filter is in force, and esc clears it and takes it down
         s = toggle SidebarPanel collapse
         x = collapse cards to one-line summaries, or expand them again
    Ctrl+P = command palette — app-level actions, including configuration
q / Ctrl+Q = quit
         ? = help screen — bindings reference
```

#### Key bindings (task detail, once `Enter` opens it)

```
←/→ or h/l = show the card selected in the adjacent column
↑/↓ or j/k = show the next or previous card in this column
 ⇧ + those = scroll the body of the task shown
         e = edit the task shown
 q/Esc/Ent = close
```

#### Key bindings (column header, once `c` reaches it)

```
         r = rename this column, in a field that replaces its label
         n = new column, named in a draft drawn to the right of this one
         d = delete this column (confirm modal)
      ⇧←/→ = move this column along the board
←/→ or h/l = move along the header strip
    c, Esc = return focus to the cards below — `c` both enters and leaves
       Tab = on to the next column's header
```

#### Key bindings (move mode, once `m` pressed)

```
←/→ or h/l = move card to adjacent column
↑/↓ or j/k = reorder card within current column
     Enter = commit — single move_task/reorder call
       Tab = show column list
       Esc = cancel — discard, no calls made
```

#### Key bindings (board switcher, once `b` pressed)

```
       ↑/↓ = move through the boards
any letter = jump to the board whose slug starts with it
     Enter = switch to the highlighted board
         N = new board, named in a row appended to the list
         R = rename the highlighted board, on its row
         D = delete the highlighted board (confirm modal)
       Esc = close, or cancel the name being typed
```

### Refresh Strategy

The filesystem remains the source of truth for the TUI, and the TUI consumes the kanban service exclusively, which itself queries the filesystem, no different from the CLI or REPL, but because the TUI maintains a visual state in a running application while the filesystem might change, it becomes necessary to develop a data refresh strategy. Our approach is twofold:

1) **After own mutations** — every create/edit/move/delete re-fetches from KanbanService immediately, so the TUI never shows stale data caused by its own actions.

2) **Manual refresh key** (`r` or `:refresh`) — the user asks for a re-sync when they know something has changed outside the app.

The TUI does **not** refresh when the terminal regains focus. Textual exposes app-level focus/blur events, but re-syncing on them redraws the board whenever the user tabs back from another window, which is disruptive more often than it is useful.

In addition the TUI will refresh whenever a git sync is executed from within the app, akin to refreshing after a mutation.

#### Refresh Only What Changed

A refresh is scoped to the components the operation could actually have affected. Never re-render a component to pick up a change that cannot have reached it — redrawing the whole screen for a local change costs the user a visible flicker and loses scroll position, selection, and focus.

For the board this means **column refreshes are limited to the columns an operation touches**:

- creating a task re-queries and redraws only the column it was created in
- deleting a task, only the column it was deleted from
- editing a task, only the column it is in
- moving a task, only the source and destination columns — and only one when the task is reordered within a column
- archiving a task, only the columns on screen it left and joined — with the archive hidden, only the one it left

While a move is being staged the same rule applies to the preview: only the column the card is leaving and the column it is joining are redrawn as it travels, never the intervening ones.

Reordering a column redraws nothing at all: where two columns sit is the only thing that changed, so the panel is moved within its container with `move_child` and the two are handed their new `Column` records. Every card, scroll position, and the focused header survive because none of them is built again.

Showing or hiding the archive column follows the same rule from the other direction: one panel is mounted at the column's place on the board, or removed from it, and the columns beside it are never rebuilt. Focus only moves when the column it was on is the one leaving.

A command run from the command bar is scoped the same way, which means the board must be told what the command did: a line of text and a parsed command line do not say which column a task ended up in. The renderer is where the two are still together — every handler hands it the object the service returned — so `TUIRenderer` records a `CommandEffect` alongside the output it captures, and the board drains both. A command that only read leaves the board alone; one that wrote a task redraws the columns it left and joined; a board or column created, renamed, reordered, or removed rebuilds. Every renderer call is classified one way or the other, and a test holds the two halves together so a command cannot be added to one without the other.

Rebuilding the entire board is reserved for changes whose effects are not confined to known columns — switching boards, a column being added, renamed, or removed — and for the manual refresh key, which exists precisely to re-read everything. A targeted refresh should fall back to a full reload when it cannot establish that its assumption holds, such as when a named column is not on screen.

The same principle governs everything else the TUI draws: a widget is handed new data only when its own data changed, and a redraw is skipped altogether when the new data matches what is already displayed.

## Config and Userdata

Configuration values are addressed by a `section.key` keypath. The keys, the values they permit, and their defaults are defined in `kanban.models.config`, which sits below both the service and the repository because both need them — the service to validate, the repository to seed a new config file. `KanbanService.get_config`/`set_config` raise `InvalidConfigKey` for a key outside `CONFIG_KEYS`, and `set_config` raises `InvalidConfigValue` for a value outside the set a key draws from (`CONFIG_VALUES`; a key with no entry there takes free text). `KanbanService.list_config` returns every supported keypath with its value (None when unset), which is what `kanban config list`, the bare REPL `config` command, and REPL tab completion of keys report.

`init_local_data` writes `CONFIG_DEFAULTS` into the config file, so a new repository starts from stated settings rather than an empty file. It is idempotent: a setting that already carries a value keeps it, and a key with no default (a name has no sensible stand-in) is left unset.

Config and user data contain different kinds of data.

Config is reserved for values that can be set by the user. Global configuration values can be placed in the user's home directory under `~/.kanban/config` and will be overriden by local configuration values.

User data contains settings that cannot be changed by the user and which are generally set by the kanban service in response to user actions, for example the currently selected board.

### Config Key-Value Pairs

```INI
[user]
    # the name of the user, used when creating a task or comment
    # no default: unset until the user sets it
    name = "philip"

[new-task]
    # where in its column a newly created task is inserted
    # values: top | bottom | above | below, default: bottom
    # above/below are relative to the selected task
    insert = bottom

[tui]
    # the theme the TUI opens in, rewritten whenever the theme changes
    # default: textual-dark
    theme = textual-dark

    # which of the TUI's notifications are shown as toasts
    # values: all | errors | none, default: all
    notifications = all

[repository]
    # the folder in the repository that contains the kanban store
    worktree = ".kanban-store"
    # the git branch associated with the worktree
    branch = "kanban"
```

### Userdata Key-Value Pairs

```INI
[user-context]
    # the currently selected board
    board = main
```
