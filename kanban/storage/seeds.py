"""Bootstrap seed data for a fresh kanban store."""

from __future__ import annotations

from typing import TypedDict


class BootstrapSeed(TypedDict, total=False):
    """A single task entry for the bootstrap seed."""
    title: str       # required
    slug: str        # required
    column: str      # required
    priority: str
    assignee: str
    body: str


class BootstrapConfig(TypedDict):
    """Full configuration for bootstrapping a new repository."""
    boards: list[dict]
    usercontext: dict[str, str]


BOOTSTRAP_CONFIG: BootstrapConfig = {
    "usercontext": {
        "board": "main",
        "column": "todo",
    },
    "boards": [
        {
            "name": "main",
            "slug": "main",
            "columns": ["todo", "in-progress", "in-review", "done"],
            "tasks": [
                {
                    "title": "list your boards and tasks",
                    "slug": "list-your-boards-and-tasks",
                    "column": "todo",
                    "body": (
                        "Use `ls` to list tasks in the current context."
                        " Navigate with `cd`:\n\n"
                        "    cd /main\n"
                        "    ls\n\n"
                        "    cd /main/todo\n"
                        "    ls"
                    ),
                },
                {
                    "title": "create a new task",
                    "slug": "create-a-new-task",
                    "column": "todo",
                    "body": (
                        "Create a task in the current column with `new task`:\n\n"
                        '    new task "Fix the login bug"\n'
                        '    new task "Write API docs" --priority high --assignee alice'
                    ),
                },
                {
                    "title": "move a task to another column",
                    "slug": "move-a-task-to-another-column",
                    "column": "todo",
                    "body": (
                        "Move a task to another column with `mv`:\n\n"
                        '    mv "fix the login bug" in-progress\n'
                        '    mv "fix the login bug" /main/in-review'
                    ),
                },
                {
                    "title": "update a task with details",
                    "slug": "update-a-task-with-details",
                    "column": "in-progress",
                    "priority": "high",
                    "assignee": "alice",
                    "body": (
                        "Update a task's metadata with `update`:\n\n"
                        '    update "update a task with details" --priority medium --assignee bob\n'
                        '    update "update a task with details" --tag bug --due-date 2026-07-01'
                    ),
                },
                {
                    "title": "go for a bike ride",
                    "slug": "go-for-a-bike-ride",
                    "column": "done",
                },
            ],
        },
    ],
}
