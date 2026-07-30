---
id: ca580129-fa12-4dda-b496-4e2ba04a7fcf
title: Task paths do not need the column
slug: task-paths-do-not-need-the-column
created_at: 2026-07-23T18:19:56.699146+00:00
updated_at: 2026-07-24T07:36:25.772484+00:00
tags: [chore, v0.6]
---

# Description

- `task-command <task>` instead of `task-command <col>/<task>`
- existing slug checks across all columns
- slug completion works across columns
- path resolution must identify the column
- only affects task commands

## Affected Kanban Services

All of these methods now take a `path: Path` argument that we can type to `path: Path | Slug`. If it's a slug find the coolumn and build the `Path`.

- get_task
- rename_task
- edit_task
- update_task
- move_task
- reorder_task
- delete_task
- assign_task
