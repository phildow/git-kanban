---
id: 2d35d686-2570-4479-94c0-c6e90fc1842d
title: Rework REPL commands
slug: rework-repl-commands
created_at: 2026-07-10T05:50:21.345170+00:00
updated_at: 2026-07-31T07:21:53.869615+00:00
tags: [repl, feature, major]
---

# Description

- Continue to organize files in folders on the filesystem
- Preset a flat hierarchy: context is board only

- [x] `cd` only sets active board
- [x] `ls` lists all tasks in the active board
- [x] `ls col` lists all tasks in the colummn same as now
- [x] `ls --boards` lists boards
- [x] `ls --columns|cols` lists columns
- [x] `new task col name` create a new task in the column
- [x] `columns|cols` lists columns
- [x] `boards` lists boards
- [x] `tasks` list tasks
- [x] remove `board` command to set the board
- [x] remove `column` command to set the col

On Hold

- [ ] `new col dest` creates a new task in the column eg `new todo "Update REPL"`
- [ ] `new --board name` creates a new board
- [ ] `new --column|col name` crteates a new column
- [ ] `delete dest` deletes task
- [ ] `delete --board name` deletes board
- [ ] `delete --column name` deletes column

Paths

- [ ] Path completion complets all tasks in the board, eg `mv x y`
- [ ] When creating a new task check path against all paths
- [ ] When listing tasks the title is the board or the column not "Tasks"
