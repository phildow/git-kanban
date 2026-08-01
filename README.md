
# Terminal Kanban

Kanban for engineers. Git-backed, Markdown-based kanban for your terminal.

Run it as a first class CLI, REPL, or TUI.

Requirements:

- Modern terminal emulator
- Python 3.13

## Install From Source

From the repository's root directory run:

```
$ pip install -e .
```

I recommend creating a virtual enviornment first and installing into it:

```
$ python -m venv .venv
$ pip install -e .
```

## Version Map

- 0.6 - CLI and REPL stable
- 0.7 - Implement the TUI
- 0.8 - Implement git tracking
- 0.9 - Implement indexing and search
- 1.0 - Release

## Motivation

After some initial success with coding agents at work I wanted to see how far I could get building an application from scratch. I settled on a kanban applicaton for the terminal involving a CLI, REPL, and TUI. I thought it was both small enough in scope to be approachable and large enough in scope to be a challenge. I liked the idea of building a terminal application, being a tool I use daily in my work, and I love the idea of replacing Jira boards.

Agents do 90% or more of the coding. I switch between Copilot with Anthropic models and Claude Code.

 I occasionally hand code features or make changes across components to ensure I continue to understand the system. I hand-coded most of the initial typing with `mypy` for v0.6, which further clarirfied the use of the `Path` and `Slug` types and significantly improved the design of the services layer, CLI, and REPL.

 Typing is good.

## Dogfooding

With v0.5 I began dogfooding the project. I moved most of the TODOs out of the README where I was tracking them and into a kanban board saved in this repository. That work is on the `kanban` branch, which per dicussions with Claude is set up as a git worktree. See CLAUDE.md for more information about git worktrees and how this project uses them.

**Try it yourself:**

Having already installed from source, and from the project's root directory, check out the `tui` branch:

```
$ git checkout tui
```

Git integration isn't set up yet, so associate the .kanban-store directory with the kanban worktree:

```
$ git checkout kanban
$ git checkout main
$ git worktree add .kanban-store kanban
```

And run the TUI:

```
$ kanban tui
```

## Claude Dekstop Conversations

Before writing any code I had a number of discussions with Claude about the pros and cons of my initial design choices. The conversations led to architecture decisions, design patterns, and UI choices.
Much of the CLAUDE.md file is composed of Claude responses during these conversations and later iterated on. I return to and develop the conversations as I work on the project.

I've included these conversations to provide some insight into the upfront work invovled in this project along with insights into my decision making process and into how I interact with Claude outside of actual coding.

## Lessons

I firmly believe that we should build tools that augment human intellgence rather than replace it. I want agents to write code for humans, not other agents, and I want to remain in the loop, making architectural decisions and also checking that I understand what is being produced.

I've learned a number of lessons from this project:

- Architecture and specification are more important with agentic coding, not less
- Agentic coding is addictive with slot machine like mechanics: sometimes excellent, sometimes a giant mess
- You'll know when you've underspecified, the quality is worse. Pause and return to design
- Take it one piece at a time
- I talk architecture and design with Claude before writing code, and I do this in the desktop app
- My loop is Design with Claude -> Claude Code | CoPilot -> Refactor & Test -> Repeat
- Review the diffs and tests, write your own commits
- Refactor often, the battle against entropy is real
- Trust, but verify
- Garbage in, garbage out

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

## Changelog

### v0.7

- The TUI
- Configuration
- Default configuration
- Comment headings

### TODO

CONFIG

- ~~Tabcomplete config keys~~ (done)
- Allow the user to alias repl commands in the config file
    - eg `c=create`
- ~~Allow the user to set a name to use for default created_by~~ (done: `config set user.name philip`)
- Use the configured `user.name` as the default assigned_to as well
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