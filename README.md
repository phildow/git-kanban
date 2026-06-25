
# Git Kanban

The repository uses pyenv and virtualenv. Run `.venv/bin/activate` to activate the virtual environment.

## Version Map

0.5 - Implement filesystem basics
0.6 - Complete filesystem and in memory store
0.7 - Implement indexing and search
0.8 - Implement git tracking
0.9 - Implement the TUI
1.0 - Release

## Lessons

- Architecture and specification are more important not less
- It is addictive with slot machine like mechanics: sometimes excellent, sometimes a giant mess
- You'll know when you've underspecified, the quality is worse. Pause and return to design
- Take it one piece at a time
- I talk architecture and design with Claude before writing code
- My loop is Design with Claude -> Claude Code | CoPilot -> Refactor -> Repeat
- Review the diffs and tests, write your own commits


## Installation

The preferred method requires pyenv and pyenv-virutalenv. They should be set up to activate the python environmment when you cd into this directory. Install pyenv and pyenv-virutalenv with homebrew, following the instructions to update your shell:

```
$ brew update
$ brew install pyenv
$ brew install pyenv-virutalenv
```

Clone the repo cd into the git-kanban/kanban directory. That should activate the virutal python environment.

```
$ git clone ...
$ cd git-kanban
(.venv) $ 
```

Finally install the local copy of `kanban` into your virtual environment and have a look at the local kanban boards:

```
(.venv) $ pip install -e kanban -q && which kanban && kanban repl
(.venv) $ kanban repl
kanban (main)>
```

Run:

```
(.venv) $ kanban init --bootstrap
(.venv) $ kanban repl
```

### TODO

0.5 - Complete filesystem

- MAJOR: Specify the data model, clarify use of slugs as source of truth, created once,
    - slugs owned by service layer

- CHORE: slug_it and only done once in the service layer at creation!
- TYPE: slug
- CHORE: remove default columns from the service layer
- BUG: task.board and task.column are ambiguious - are the names or slugs

- FEAT: add mutually exlusive argument to move command to move to top or bottom: --top | --bottom | board
- BUG: raise a services domain error if you rename to the same name
- BUG: rename column double appending board

- CHORE: special camel case for To Do -> todo not to-do
- FEAT: consider case-conversion package for unicode compatible kebab casing (pycases)
- FEAT: kebab_case preserves accented characters

- Add documentation explaining the move only moves task from one column to another
- Add documentation explaining that names and titles are always slugged for the filesystem, that
  they are treated as slugs in the cli and repl but displayed using their names and titles with
  the --list flag (this may be a weakness in the system or at least confusing)
- But once we're running TUI the user won't see the underlying implementation

~

0.6: Complete in memory store 

- Ensure memory store supports same features as filesystem (ordering)
- Handle special characters in slugs

~


- FEAT: think about how move should work, for example should the dest allow it to rename, or is it more natural to just give it a column
        and use rename to rename a task, although that breaks mv dynamics (or require a mutal flag)
        and if the dest for move is a column or board/column then autocomplet has to take that into account
- BUG: handle path errors better

- TEST: Check init error handling, don't overwrite a repo, don't initialize a repo that's already been created

- FEAT: add csv export
- FEAT: add closed_at metadata to a Task
- FEAT: config: default boards that automatically set the closed_at value: None until moved to done or archived if None

- TEST: make sure repl gives recoverable error messages

- BUG: `kanban (/) > ls main -al` returns an error probably a mutually exlusive argument `kanban (/) >`

- FEAT: give the user the option to bootstrap from the repl
- CLAUDE: note that models are lightweight and do not include relationships, where they reference other entities they reference them by name only, always call a service layer method to get a fully qualified object

- CHORE: always pass the path to get_tasks not a reconstructed path
- CHORE: basic refactoring to use exists methods in the filesystem, i'm sure there's more
- CHORE: add utilty to filter for invisible files, which is used extensively in the filesystem repo
- CHORE: Use slugs in memory repository for private indexing (add tests)

POTENTIAL INCONSISTENCY

- Where metadata is required, eg sort order, files may be missing or renamed directly, change not reflected in metadata file
- The file system is the source of truth, although metadata or the index may be out of sync.
- Corrections defer to the filesystem, eg sort: 
-   If the filename appears in the metadata but not the folder, remove it from the metadata
-   If the filename appears in the folder but not the metadata, add it to the back
- Two kinds of syncing:
-   Filesystem -> cache | metadata
-   Filesystme <-> git

- FEAT: implement user sort order for columns
- FEAT: implement user sort order for tasks

- FEAT: bump command to move a board or task to the front
    - => think of the equivalent interaction for the TUI
    - => press m to move and then the arrows keys to move up/down between boards, shift key to top/bottom
    - => Use of proper names instead of slugs (filenames)
    - => 

- FEAT: tab completion for assigness and tags
- FEAT: ooo the shell will make as few as two columns
- FEAT: Add comments to a task which are just appended to the body

- CHORE: Models return a path?

CONFIG

- Tabcomplete config keys?
- Allow the user to alias repl commands in the config file
    - eg `c=create`
- Allow the user to set a name to use for default createdb_by and assigned_to (get this from get config if available)
    - eg `name=philip`
- Allow the user to set their preferred editor?
- Allow the user to decide what columns are shown for a given terminal size when listing tasks
    - eg `task-cols:80=title,assigned-to,tags`
    - eg `task-cols:96=title,assigned-to,tags,due`
- Allowe the user to customize the default column names

- Once we have file storage `kanban init` this directory and start storing tasks here (dogfood) ~ almost there!
- Which takes us to git integration

VERSION 1.1

- Globbing for path commands

AGENT KANBAN

- watches your work and manages the tasks for you via the `kanban` cli
- Check out a task it checks out a branch and vice versa
- Check out a branch it looks for the task to check out

HISTORY (TUI)

- A visual representation in a view to the right when there is enough terminal size

### Running tests:

TOOD: is this right?

```
python3 -m unittest discover -s tests
```

### Installing after changes

```
pip install -e . -q && which kanban && kanban --help
```

```
.venv/bin/pip install -e . -q && which .venv/bin/kanban && .venv/bin/kanban --help
``` 