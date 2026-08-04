# Sync

Date: 20260624_071610

ID: 994173d1-5f5a-4a33-aef6-f9857affce40


**User**: [2026-06-24 07:13:34]

Let’s take a look at keeping a running REPL or TUI in sync with the filesystem. 

In a previous conversation we settled on this strategy:

Refresh strategy: self-mutation + focus-return + manual fallback

1. After own mutations — every create/edit/move/delete re-fetches from KanbanService immediately, so the TUI never shows stale data caused by its own actions.

2. On terminal focus return — when the app detects the terminal window regained focus (via terminal focus-reporting escape sequences, exposed through Textual’s app-level focus/blur events), it re-syncs from the filesystem. This catches the common case of switching away to run git pull or edit a file, then switching back.

3. Manual refresh key (r or :refresh) — explicit fallback for when focus-tracking isn’t supported (notably gaps in tmux/screen pass-through) or when something changes while the terminal stays focused the whole time.

---


**Claude**: [2026-06-24 07:13:47]

This strategy as written is TUI-specific (Textual focus/blur events). For the REPL, there's no persistent screen redraw to worry about, but there's still a long-lived process that could see stale index/filesystem state between commands.

A few things worth clarifying before going further:

1. **Does this apply to REPL at all?** Since the index is always re-queried per `KanbanService` interaction, and the REPL doesn't render anything until a command runs, is there a meaningful staleness problem for the REPL beyond "did the index need to be refreshed before this command runs"? Or is "REPL or TUI" really just "TUI" and the REPL is unaffected?

2. **What layer owns the refresh?** Self-mutation re-fetch and manual refresh are app-layer (CLI/REPL/TUI) concerns calling back into `KanbanService`. But "refresh" presumably means: tell `IndexService` to re-sync from filesystem, then re-query. Where does that re-sync call live — does `KanbanService` expose an explicit `refresh()`/`resync()` method, or does every read just always re-scan relevant paths and the index becomes irrelevant on refresh?

3. **Scope of refresh** — full re-scan of the whole `.kanban-store`, or scoped to what's currently visible (active board/column, or only paths touched)? Given "filesystem is source of truth" and "index is a cache," a focus-return refresh could be expensive on large stores if it's a full rescan vs. a targeted check (mtime/hash comparison).

Which of these do you want to dig into first?

---

