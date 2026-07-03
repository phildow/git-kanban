---
id: 2a3b2325-4e80-43dc-9c2c-4230d9309153
title: All paths are absolute in CLI
slug: all-paths-are-absolute-in-cli
created_at: 2026-07-02T22:54:58.913259+00:00
updated_at: 2026-07-02T22:59:28.742245+00:00
assigned_to: philip
tags: [bug]
---

# Description

Because the CLI uses the kanban service it uses the current working directory, but all CLI paths are implicitly absolutely even if they don't start with a forward slash.

Which is why I'm getting errors like this when I try to list all the tasks in a board with 

```
$ kanban task list main
Error: Column not found: main/main
```
