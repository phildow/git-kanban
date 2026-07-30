
# Git Kanban

Kanban for engineers. Git-backed, Markdown-based kanban for your terminal.

The repository uses pyenv and virtualenv. Run `.venv/bin/activate` to activate the virtual environment.

## Version Map

- 0.6 - CLI and REPL stable
- 0.7 - Implement indexing and search
- 0.8 - Implement git tracking
- 0.9 - Implement the TUI
- 1.0 - Release

## Claude Dekstop Conversations

I engange in archiceture and design discussions about the project in the Claude Desktop app. I've included those conversations here for reference. 

Before writing any code I had a number of discussions with Claude about the pros and cons of my initial design choices. The conversations led to architecture decisions, design patterns, and UI choices.
Much of the CLAUDE.md file is composed of Claude responses during these conversations and later iterated on. I repeatedly return to and develop the conversations as I work on the project.

I've included these conversations to provide some insight into the upfront work invovled in this project along with insights into my decision making process and how I interact with Claude outside of actual coding.

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

0.6: Error handling, Complete in memory store

Error Handling

- CHORE: Does the repo raise not found errors or does the service layer?
    - I think the orchestrator just orchestrates and propogates errors but lets the storage layer determine if there is an error
- FEAT: Use specific errors when a board/column/task isn't found
- FEAT: Only show an "Unepected Error" when it actually is, vs say renaming to a name that already exists 
- TEST: handle path errors better

- FEAT: consider case-conversion package for unicode compatible kebab casing (pycases)
- FEAT: kebab_case preserves accented characters

~

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
- Allow the user to configure rich layout properties (eg table box style)
- Allow the user to customize the rich colors (Theme)
- Allow the user to render markdown normally

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
python -m unittest discover -s tests
```

### Static type checking (mypy)

Install development dependencies and run mypy:

```bash
pip install -e ".[dev]"
python -m mypy
```

### Installing after changes

```
pip install -e . -q && which kanban && kanban --help
```

```
.venv/bin/pip install -e . -q && which .venv/bin/kanban && .venv/bin/kanban --help
``` 