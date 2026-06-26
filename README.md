
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

- FEAT: rename renames a task as well
    - Flag not required
    - But we should be able to just give the slug and from the path determine what we are renaming, dispatch accordingly
    - CLI & REPL

- CHORE: remove default columns from the service layer
- BUG: default "To Do" slug -> todo

- TEST: Check init error handling, don't overwrite a repo, don't initialize a repo that's already been created
- TEST: make sure repl gives recoverable error message

- FEAT: consider case-conversion package for unicode compatible kebab casing (pycases)
- FEAT: kebab_case preserves accented characters

~

- Once we have file storage `kanban init` this directory and start storing tasks here (dogfood) ~ almost there!

~

0.6: Complete in memory store 

- TEST: Ensure memory store supports same features as filesystem (ordering)
- TEST: handle path errors better
- FEAT: `--exlude` flag to list when `--all` flag to exlude a column (support multiple)
- CHORE: Use slugs in memory repository for private indexing (add tests)
- CHORE: add utilty to filter for invisible files
- FEAT: ooo the shell will make as few as two columns
- FEAT: add csv export
- BUG: raise a services domain error if you rename to the same name

- FEAT: Add comments to a task which are just appended to the body
    - CLI: `task comment <board/column/task> <comment>`
    - REPL: `comment <task> <comment>`
    - Need to note who left it

~

- FEAT: add closed_at metadata to a Task
- FEAT: config: default boards that automatically set the closed_at value: None until moved to done or archived if Nones

- FEAT: give the user the option to bootstrap from the repl
- CLAUDE: note that models are lightweight and do not include relationships, where they reference other entities they reference them by name only, always call a service layer method to get a fully qualified object

- CHORE: always pass the path to get_tasks not a reconstructed path
- CHORE: basic refactoring to use exists methods in the filesystem, i'm sure there's more

POTENTIAL INCONSISTENCY

- Where metadata is required, eg sort order, files may be missing or renamed directly, change not reflected in metadata file
- The file system is the source of truth, although metadata or the index may be out of sync.
- Corrections defer to the filesystem, eg sort: 
-   If the filename appears in the metadata but not the folder, remove it from the metadata
-   If the filename appears in the folder but not the metadata, add it to the back
- Two kinds of syncing:
-   Filesystem -> cache | metadata
-   Filesystme <-> git

INDEXING

- FEAT: tab completion for assigness and tags

TUI

- FEAT: implement user sort order for columns
- FEAT: implement user sort order for tasks

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
- Allow the user to customize the default column names

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