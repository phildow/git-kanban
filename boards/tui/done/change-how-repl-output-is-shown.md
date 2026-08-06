---
id: 34463d8c-01c1-4bb6-a6ac-fee4f43d5eb5
title: Change how repl output is shown
slug: change-how-repl-output-is-shown
created_at: 2026-07-31T08:46:20.393330+00:00
updated_at: 2026-08-04T20:58:15.086792+00:00
priority: medium
tags: [v0.7]
---

# Description

Instead map the commands to toasts matching the tui equivalents. This means we have to update the mapping with every new command.

Or we just have a `TUIRenderer` that conforms to the `CommandRenderer` and emits TUI friendly messages. They could be toasted, but ah they won't have the same styling as the TUI action toatst. Still

Catch erorrs and display them differently

# Comments

## 2026-08-03 @phildow

Or show output in a different way, with improved formatting

## 2026-08-04 @phildow

What about a panel that is placed over the command bar and which prints the results there

## 2026-08-04 @phildow

Settled on an output panel that appears immediately above the command bar and in the same style, looks great.
