
# Git Kanban

The repository uses pyenv and virtualenv. Run `.venv/bin/activate` to activate the virtual environment.

## Version Map

0.5 - Implement filesystem basics
0.6 - Complete filesystem and in memory store
0.7 - Implement indesing and search
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

### TODO

- check init
- check init error handling
- move search_tasks to the index service
- add utilty to filter for invisible files, which is used extensively in the filesystem repo

- Use slugs in memory repository for private indexing (add tests)
- Models return a path
- Cleanup: Define some getter methods as properties
- Add comments to a task which are just appended to the body

TAB COMPLETION

- Swing back around to path completion in svc._rewrite_relative_paths (eg cd, ls)
- Assignees, priorities, and tags are cached in the index
- Double tab to cycle through completions

- Commands
- Paths relative and absolute
- Flags?
- Assignees
- Priority
- Tags

TESTS

- Make sure create board converts name to slug and uses that for filename
- Make sure create column converts name to slug and uses for filename

CONFIG

- Tabcomplete config keys?
- Allow the user to alias repl commands in the config file
    - eg `c=create`
- Allow the user to set a username to use for default createdb_by and assigned_to
    - eg `username=philip`
- Allow the user to set their preferred editor?
- Allow the user to decide what columns are shown for a given terminal size when listing tasks
    - eg `task-cols:80=title,assignee,tags`
    - eg `task-cols:96=title,assignee,tags,due`
- Allowe the user to customize the default column names

- FileStorage
- Use `.kanban` for configuration and caching and `.kanban-store` for the filesystem
- Once we have file storage `kanban init` this direcory and start storing tasks here (dogfood)
- Which takes us to git integration


- Agent Kanban `agent-kanban` watches your work and manages the tasks for you via the `kanban` cli
    - Check out a task it checks out a branch
    - Check out a branch it looks for the task to check out

HISTORY

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