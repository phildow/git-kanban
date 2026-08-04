---
id: 68983609-09f1-48c3-8bb8-44bd931fb639
title: First run on downloaded repo reports not initialized
slug: first-run-on-downloaded-repo-reports-not-initialized
created_at: 2026-07-31T18:38:58.398080+00:00
updated_at: 2026-08-04T07:19:19.815935+00:00
priority: high
tags: [v0.7, bug]
---

# Description

Just grabbed the repository on another machine, set up the venv and ran `kanban repl` but the repl reports that kanban is not initialized.

# Comments

## 2026-07-31 @phildow

Break up initialization into two parts:

1) kanban store initialization
2) kanban local data initialiation

Consider a repo initialized if the kanban store has been set up. If local data has not been set up, which can be the case when a repo is cloned, then set it up with default values and handle missing values, eg the active board.
