---
id: 35f5d465-51b5-480a-92f7-d7a9b88ee737
title: Command to add comments to a task
slug: command-to-add-comments-to-a-task
created_at: 2026-06-30T20:24:31.958450+00:00
updated_at: 2026-06-30T20:28:19.914587+00:00
tags: [feature]
---

# Description

CLI:  `task comment <board/column/task> <comment>
REPL: `comment <task> <comment>`

Note who left it, for example:

# Comments

@phildow
This is a sample comment. It begins under the Comments header, which is how we parse for it, and each new comment begins with an @ or some other signifier to indicate this is the start of a comment.

A comment can have newlines and the next comment begins with the next @ signifier. Would be cool if we could have midmatter in addition to front matter.

@marie
An example second comment in response to the first one. Always appended to the markdown body.
