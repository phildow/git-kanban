---
id: 0a294ae8-0bc7-420d-862c-9ec39781ab4e
title: fileystem.move_task returning board and column name
slug: fileystemmove-task-returning-board-and-column-name
created_at: 2026-07-02T06:00:41.038751+00:00
updated_at: 2026-07-30T23:20:06.382202+00:00
tags: [bug]
---

# Description

Render move_task uses result.column which should be the slug but is the name.

We actaully want the name but we should be getting it from the slug.
