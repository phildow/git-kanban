
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

- add --list flag to ls to provide more details
- Is the show command not working?
- Swing back around to path completion in svc._rewrite_relative_paths

- REPL != CLI
    - The repl does not support the same commands as the CLI
    - The repl has its own commands, parser, and renderer
    - It is not a verb first or noun first difference, it is interactive
    - It has its own dedicated parser with a more limited set of commands, mirroring those of the terminal:
        - cd (use)
        - ls (list)
        - mv (rename or move)

- REPL
    - Remove init (check that we're in a kanban directort at init and ask user if they'd like to init if not)
    - Simplify repl commands, they mostly take a path
    - Most only takes a path not a noun object - the whole noun first cli got me its a terminal emulator
    - Double tab to cycle through completions
    - But the way readline works it seems that whatever you provide to be shown as options also becomes the completion

- REPL Additional commands
    - some way to set metadata
    - assign {task} {person}

CONFIG

- Allow the user to alias repl commands in the config file
    - eg `c` or `n` for `create`
    - eg `l` for `list`
- Allow the user to set a username to use for default createdb_by and assigned_to
- Allow the user to set their preferred editor

- Add comments to a task which are just appended to the body

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
python3 -m unittest discover -s tests
```

### Installing after changes

```
pip install -e . -q && which kanban && kanban --help
```

```
.venv/bin/pip install -e . -q && which .venv/bin/kanban && .venv/bin/kanban --help
``` 