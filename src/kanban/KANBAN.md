# Kanban

This project uses [kanban](https://github.com/phildow/git-kanban), a git-backed,
markdown-based task manager for the terminal. This file was written when the
repository was initialized. It is yours — edit or delete it.

## Where Your Data Lives

```
.kanban-store/                    # shared board state, tracked by git on its own branch
└── boards/
    └── main/                     # a board is a directory
        ├── todo/                 # a column is a subdirectory
        │   └── fix-login-bug.md  # a task is a markdown file
        └── archive/

.kanban/                          # local machine state — config, history, search index
```

A task's fields are frontmatter in its markdown file; its description and
comments are the body. Board and column settings — display names, column order,
task order — live in a hidden `.metadata` file in each directory.

`.kanban-store/` is a git worktree checked out on the `kanban` branch, so board
history is tracked separately from your project's history. `.kanban/` is
machine-local and disposable; it is not shared.

## Change Data Through Kanban

The filesystem is the source of truth, and markdown is a format you can read. 
Still, use the application to make changes rather than editing 
files directly:

- Every task carries a UUID and timestamps that kanban maintains
- A task's filename is a slug of its title — renaming the file does not rename the task
- Column and task order is recorded in `.metadata`, not by the filesystem
- Kanban keeps a search index in sync with each write, and commits changes to git
- Markdown is formatted for metadata and to distinguish content

Reading files, grepping them, and viewing them in your editor are all fine.

## Three Ways to Use It

### TUI — Kanban in the terminal

```
$ kanban tui
```

Keyboard driven. `←/→` and `↑/↓` (or `h/j/k/l`) move between columns and cards,
`n` creates a task, `e` edits one, `Enter` opens it, `m` moves it, `a` archives
it, `b` switches boards, `/` opens a command line, `:` filters as you type,
`?` lists every binding.

### REPL — An interactive shell

```
$ kanban repl

kanban () > board main
kanban (/main) > tasks todo
kanban (/main) > new todo "Add rate limiting" --priority high --assigned-to alice
kanban (/main) > move add-rate-limiting in-progress
kanban (/main) > view add-rate-limiting
```

The active board is your working directory, so paths are relative to it and
tasks are named by slug alone. `Tab` completes commands, flags, slugs, tags, etc.

### CLI — One command per invocation

```
$ kanban task list /main/todo
$ kanban task create /main/todo "Fix login bug" --priority high --tag auth
$ kanban task move /main/todo/fix-login-bug in-progress
$ kanban task comment /main/todo/fix-login-bug "Investigating."
$ kanban search "login" --assigned-to alice
```

Paths are absolute: `/board/column/task`. Add `--format json` to script against
the output.

## Configuration

```
$ kanban config list
$ kanban config set user.name alice
```

For example `user.name` is recorded as the author of the tasks and comments you create.

## Onboarding Someone Else

`.kanban-store/` is a worktree, so a fresh clone has to attach it:

```
$ git checkout kanban
$ git checkout main
$ git worktree add .kanban-store kanban
```

This will be automated in the future.

Run `kanban --help`, or `?` in the TUI, for everything else.
