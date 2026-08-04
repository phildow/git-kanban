---
id: a7f9d844-f467-4f8c-bf12-82c9d9256717
title: URL handlers
slug: url-handlers
created_at: 2026-08-01T00:38:34.466458+00:00
updated_at: 2026-08-03T22:54:30.664409+00:00
priority: medium
tags: [feature]
created_by: phildow
---

# Description

Execute the CLI, REPL, or TUI with a `kanban://` URL:

```
kanban kanban://path/to/task
```

```
kanban repl kanban://path/to/task
```

```
kanban tui kanban://path/to/task 
```

CLI prints the object, REPL switches to that board and prints the object, TUI switches to the board and selects/opens the object.
