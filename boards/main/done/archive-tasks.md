---
id: dbec19d8-7bf3-4401-930b-97a3b461c2e9
title: Archive tasks
slug: archive-tasks
created_at: 2026-07-31T03:58:36.602977+00:00
updated_at: 2026-08-05T20:41:43.874588+00:00
priority: high
tags: [v0.7]
---

# Description

Archive column. Additional field on task:

```python
archived_at: datetime | None

def is_archived(self) -> Bool:
  return self.archived_at is not None
```

Only show the field if it has a value.

Archiving/unarchiving is simply a matter of moving a task into and out of the archive column. Moving a task to the archive column updates `archived_at`. Moving it out resets that value back to `None`.

Commands that show all tasks by default do not included archived tasks, eg `tasks` in REPL. Commands that search DO include archived tasks. User can exclude archived tasks using the `--exclude` flag with the `search` command.

Treat the archive column like any other in the CLI and REPL. In the TUI hide it by default. Identify the archive column with a new `role` field whose value is `archive`. Store it in the column metadata.

CLI:

```
kanban column list <board>  # includes archive column
kanban task list <board>[/<column>]  # unscoped skips archived tasks;<board>/archive shows archived  tasks
kanban task move <board>/<column>/<task> archive # archives
kanban task move <board>/archive/<task> <column>  # unarchives
kanban search <query>  # includes archived tasks
kanban serach <query> --exlcude archive # excludes archived tasks
```

Boards (later)
```
kanban board list [--archived]
kanban board archive <board>
kanban board unarchive <board>
```

REPL:

```
tasks # unscoped skips archive column
tasks archive # shows archived tasks
move <task> archive # archives a task
move <task> column # unarchives a task
search # include archived tasks
search --exclude archive # exclude archived tasks
```

TUI:

```
a: arvhive a task # with confirmation
A: show archive column
```

# Comments

## 2026-08-03 @phildow

Going to remove the `archived_at` property from the task entirely. The commit history shows when a task is archived. So completely ignoring Claude's recommendation on this one.
