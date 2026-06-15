# Git Kanban

The repository uses pyenv and virtualenv. Run `.venv/bin/activate` to activate the virtual environment.

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
$ cd git-kanban/kanban
(.venv) $ 
```

Finally install the local copy of `kanban` into your virtual environment and have a look at the local kanban boards:

```
(.venv) $ pip install -e . -q && which kanban && kanban --help
(.venv) $ kanban repl
kanban (main)>
```

### TODO 

- Support tab completion in the repl
    - If the board is available for task list but the column is not, list all tasks in the board
    - Tab completion options include the already implied components of the path, they should only show the part under completion
    - But the way readline works it seems that whatever you provide to be shown as options also becomes the completion
- Treat `use` more like `cd`, and treat paths as relative paths
    - If a board has been set use only tab completes to the available columns
    - Unless the path begins with a leading forward slash `/`, in which case it should tabcomplete to the available boards

- Error handling
    - Resolve repository errors to service errors and catch most of them in the repl
    - Handle value errors and missing board/column errors without exiting

- Allow the user to alias repl commands in the config file
    - eg `c` or `n` for `create`
    - eg `l` for `list`
- Type the svc object that is represented by KanbanService everywhere
- Push to github
- Scaffold IndexingService ABC -> Memory and SQLite
- Scaffold GitService
- FileStorage
- Use `.kanban` for configuration and caching and `.kanban-store` for the filesystem
- Once we have file storage `kanban init` this direcory and start storing tasks here (dogfood)
- Which takes us to git integration
- Agent Kanban `agent-kanban` watches your work and manages the tasks for you via the `kanban` cli
    - Check out a task it checks out a branch
    - Check out a branch it looks for the task to check out

### Running tests:

TOOD: is this right?

```
python -m unittest -q tests/test_commands.py tests/test_kanban_service_init.py
```

### Installing after changes

```
pip install -e . -q && which kanban && kanban --help
```

```
.venv/bin/pip install -e . -q && which .venv/bin/kanban && .venv/bin/kanban --help
``` 