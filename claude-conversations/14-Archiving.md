# Git Kanban — Archiving Design Discussion

*Exported chat history*

---

## User

Archiving. I'd like to give the user the ability to archive tasks and even entire boards. Archived tasks should not be normally visible or appear in lists or searches unless specifically requested. I was thinking about adding a special archive column that is not normally visible in the tui. Are there other options for managing archived tasks?

## Assistant

A few options, each with different tradeoffs against your data model:

**Frontmatter/metadata flag (recommended).** Add `archived_at: datetime | None` to task frontmatter and an `archived` field to board `.metadata` `[fields]`. The task stays in its current column and file location — nothing moves. `task list`, `search`, and column/board task counts filter out anything with `archived_at` set unless `--archived` is passed. Boards work the same way at the `board list` level. This fits the existing pattern (columns already carry ordering metadata, tasks already carry frontmatter fields) and unifies task- and board-level archiving under one concept: archived is a property of the object, not a location. It also means unarchiving is trivial — clear the field, task reappears exactly where it was, no need to remember "which column did this come from."

**Hidden archive column (your idea).** Reuses `task move` as the archive verb, which is appealing. But it needs exceptions everywhere columns are enumerated (column list, board task_count, TUI column rendering, `.metadata` order), and it loses the task's original column — so unarchiving needs a separate "restore to previous column" mechanism, probably requiring you to stash the prior column in frontmatter anyway (e.g. `archived_from: <column>`), at which point you're doing most of the metadata-flag work regardless. It also doesn't generalize to archiving a whole board — you'd need a second, different mechanism for that case, whereas the flag approach handles both with the same shape.

**Physical relocation** (move task file into `.archive/<column>/`, or move the whole board directory into `boards/.archive/<slug>/`). Keeps active directories clean by construction — no filtering logic needed for a plain `ls`/glob. But it breaks path stability: your model treats path as a globally unique, slug-derived identifier, and moving a board out from under `boards/<slug>` either changes its path or requires special-casing the archive location as still "at" its old path. More git churn per archive/unarchive too (rename ops vs. a one-line frontmatter edit).

I'd go with the flag approach unless you specifically want archived items physically segregated from the git history's normal diff noise. One thing worth deciding either way: when a board is archived, do its tasks also get individually flagged, or does board-level archived status alone suffice to hide them from board-scoped listings and cross-board search? The former makes "unarchive a single task within an archived board" meaningless (which might be fine), the latter is simpler but means task-level archived state and board-level archived state are two separate flags a searcher has to reason about.

---

## User

I'm considering the following command structures for the CLI and REPL:

REPL

```
archive  # list archived tasks in activate board
archive <task> # archive task
archive -u <task> # unarchive task
archive -b # list archived boards
archive -b <board> # archive board
archive -u -b <board> # unarchive board
```

CLI

```
kanban board archive # list archived boards
kanban board archive /board # archive board
  -u # unarchive board
kanban task archive /board # list archived tasks in board
kanban task archive /board/col/task # archive task
  - u # unarchive # unarchive task
```

## Assistant

A few things don't line up with the conventions already established elsewhere in the spec.

**Short flags.** `-u` and `-b` break from the pattern — everywhere else uses long flags (`--column`, `--board`, `--remove`, `--force`, `--edit`). The only existing short flags are `-p/--plain` and `-b/--bootstrap` on `init`, `-h/--help` globally. Reusing `-b` for "board" here collides with `-b` already meaning "bootstrap" on `init` — not a functional conflict since they're different commands, but it means `-b` isn't a stable mnemonic across the app. The CLI section as you've written it has no short flags at all currently, so `-u` there would be the first.

**Unarchive as a new flag pattern.** The project already has a "reverse an action" idiom: `tag <task> <tag> --remove` and `assign <task> --remove`. Worth deciding whether unarchive should reuse `--remove` for consistency (`archive <task> --remove`), or whether `--unarchive`/`-u` is clearer since "remove" doesn't obviously read as "restore."

**`archive` doing double duty.** Bare `archive` lists, `archive <target>` mutates. No other verb in the REPL does this — `rename`/`delete` only mutate, `boards`/`tasks` only list, `view` only reads. It's a recognizable idiom (`git branch`, `git tag`), but it's a real departure from how every other command here behaves, so I'd confirm it's intentional rather than incidental. The alternative: keep `archive`/`unarchive` strictly as mutating verbs like `delete`, and expose "show archived" as an `--archived` filter flag on the existing `tasks`/`boards`/`list` commands — consistent with how `--priority`, `--tag`, `--assigned-to` already work as filters.

**Board targeting in the REPL.** `rename --board <new-name>` and `delete --board` both act on the currently active board via context, no board argument. Your `archive -b <board>` takes an explicit board name, bypassing context. That's a legitimate convenience, but it diverges from the established pattern where you're expected to `board <name>` first. Worth deciding if that divergence is deliberate.

**Scope of `kanban task archive` with no board.** Your spec always requires a board (`kanban task archive /board`). Did you want an unscoped form that lists archived tasks across all boards, mirroring how `kanban search` works without `--board`?

---

## User

1) There will always be long flags as well.
2) What are the pros and cons of using `-u,--unarchive` over a dedicated `unarchive` command
3) Show me the change to existing commands to include archived results with an `--archived` filter flag
4) You're right in the REPL `archive --board` archives the active board without needing to specify a board

## Assistant

1) Noted.

2) `-u/--unarchive` flag vs. a dedicated `unarchive` command:

Flag on `archive`:
- Consistent with the existing `--remove` idiom on `tag`/`assign` (one verb, a flag reverses it).
- Smaller surface: one alias to register, one command to document.
- But: `tag`/`assign --remove` removes a *sub-item* (a specific tag, a specific assignee) from a relationship. Archiving isn't that — it's a whole-object lifecycle state, closer to `delete` than to `tag`. `archive foo --unarchive` also reads oddly, since the flag negates the verb it's attached to rather than modifying an argument.
- Completion gets flag-dependent: `archive <TAB>` needs to complete active-task slugs, but `archive -u <TAB>` needs to complete archived-task slugs — the completer has to branch on a flag that comes before the positional it affects.

Dedicated `unarchive`:
- No semantic paradox, reads cleanly on its own.
- Completion is naturally scoped per-command with no flag-branching.
- Matches how other lifecycle-state pairs are usually done elsewhere (`create`/`delete` is already a pair in this spec, not `create --delete`).
- Cost: one more verb in the alias table and help output, and you still need `--board`/`--column` targeting on both verbs either way, so it doesn't reduce flag count, just moves the state toggle from a flag to a verb name.

Net: `--remove` precedent argues for a flag; `delete` being its own verb (not `create --delete`) argues for a separate command. I'd lean toward a dedicated `unarchive` since archiving is closer to delete's category than tag's, but it's a close call — your preference either way is fine since both are self-consistent with *something* already in the spec.

3) Adding `--archived` to the existing list/search commands, with `archive`/`unarchive` reduced to pure mutation verbs (no list-mode):

REPL:

```
boards [--slugs] [--archived]

tasks [<column>]
    [--slugs]
    [--exclude <column>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by|column>]
    [--reverse]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]
    [--archived]

search <query>
    [--slugs]
    [--board <board>]
    [--sort ...]
    [--reverse]
    [... existing filters ...]
    [--archived]

archive <task> | --board
unarchive <task> | --board
```

CLI:

```
kanban board list [--archived]

kanban task list <board>[/<column>]
    [... existing filters ...]
    [--archived]

kanban search <query>
    [--board <board>]
    [... existing filters ...]
    [--archived]

kanban task archive <board>/<column>/<task>
kanban task unarchive <board>/<column>/<task>

kanban board archive <board>
kanban board unarchive <board>
```

`--archived` here means "show only archived items" (mirrors the exact set your `archive` list-mode was going to return), not "show archived alongside active." If you want a combined view later that's a separate flag (`--all`), not a reason to change this now.

4) Good.

One gap this leaves: `delete` targets task, column, or board (`--column`/`--board`). Your archive design only covers task and board — no column-level archiving. Worth deciding whether `archive <task> | --column <column> | --board` should exist for symmetry with `delete`, or whether archiving a column doesn't make sense in your model (e.g. because column membership is itself just "where the task lives," not a lifecycle state worth archiving in bulk).

---

## User

Let's go with a dedicated unarchive command. Confirming that --archived only shows the archived objects. Right now it doesn't make sense to archive a column

## Assistant

Confirmed. Finalized surface:

REPL:
```
boards [--slugs] [--archived]
tasks [<column>] [...existing filters...] [--archived]
search <query> [...existing filters...] [--archived]

archive <task> | --board
unarchive <task> | --board
```

CLI:
```
kanban board list [--archived]
kanban task list <board>[/<column>] [...existing filters...] [--archived]
kanban search <query> [...existing filters...] [--archived]

kanban task archive <board>/<column>/<task>
kanban task unarchive <board>/<column>/<task>

kanban board archive <board>
kanban board unarchive <board>
```

`--archived` shows only archived objects. No column-level archiving. This is ready for you to move into implementation whenever you want — just say the word.

---

## User

For the TUI, what are some options for archiving and unarchiving and for viewing archived tasks and boards

## Assistant

Splitting this into triggering the action vs. viewing archived state, for both tasks and boards.

**Archiving/unarchiving a task.** A single toggle key on the focused card is the natural fit given the existing single-key model (`n`/`e`/`d`/`m`). `a` is unbound — same key could mean "archive" when the focused card is active and "unarchive" when it's archived, so it doesn't need a second key or a mode. Unlike `d`, this probably doesn't need a confirm modal since it's reversible. The alternative is leaving it command-bar-only (`:archive <task>`) with no dedicated key — less discoverable, but zero new keymap surface, and it already works today via the CommandBar's REPL-syntax parsing without any TUI code changes.

**Viewing archived tasks in a board.** Three shapes:
- *Inline, dimmed, toggle-visible* — archived cards render in their original column, dimmed. This is actually already implied by your existing color legend ("dim/grey for archived items"), so it may be what you'd already pictured. Needs a visibility toggle (key or palette entry) since they're hidden by default; toggling on would be a full-board refresh (falls outside the "refresh only affected columns" rule, more like switching boards).
- *Separate section/pseudo-column, TUI-only* — archived tasks (from any column) collected into one dedicated panel when toggled on. Visually distinct from the inline-dim approach, doesn't touch storage (this is purely presentational, unlike the archive-column idea you already ruled out for storage). Better if you want archived tasks grouped for scanning rather than scattered across their original columns.
- *Modal browser* — a screen like `TaskDetailScreen`/`ConfigScreen`, pushed by a key or palette entry, listing archived tasks flat with unarchive on `Enter`/`u`. Keeps the main board view untouched; costs a new screen.

**Archiving/unarchiving a board.** Given this is infrequent, it fits the command palette's stated purpose ("app-level actions... the ones with no key of their own") better than a hotkey — add an "Archive Board" / "Unarchive Board" entry alongside Configuration/Theme. Archiving the currently active board needs a fallback: same as board delete presumably does, drop back to `BoardSwitcherScreen` since there's no longer an active board.

**Viewing archived boards.** Either extend `BoardSwitcherScreen` with a toggle (a key inside the modal flips the `PrefixList` between active/archived, similar to its existing "+ New board…" row) or a sibling `ArchivedBoardsScreen` pushed from the palette. The toggle keeps it to one screen; the sibling screen matches the two-screen precedent you already have for config (`ConfigScreen`/`ConfigValueScreen`).

Open question either way: confirm modal or not for archive actions, and whether toggling "show archived" is a per-session view state or something that resets when you switch boards.

---

## User

For tasks i like the idea of having a separate section for the TUI only that is purely presentation, how do we toggle the visibility of this column, and how do we determine the order of tasks in it in a deterministic way. can the user move tasks out of the archived column and into another column.

## Assistant

**Toggling visibility.** There's already a precedent for this exact interaction — `s` toggles the sidebar panel's collapse. Same pattern here: since lowercase `a` is taken for archive/unarchive on the focused card, something like `A` toggles the archived section on/off, shown in the footer like the other bindings. Because the section aggregates tasks from every column rather than being confined to one, turning it on/off should trigger a full board rebuild under your existing refresh rules ("rebuilding the entire board is reserved for changes... not confined to known columns"), not a targeted redraw. One thing to decide: should this toggle persist across board switches within a session, or reset each time — and should it be remembered across restarts (a `tui.show_archived` config key, same treatment as `tui.theme`) or always start hidden?

**Ordering.** Since this is presentation-only, I'd avoid inventing a stored order list for it — doing so would recreate the exact column-like bookkeeping you already decided archiving doesn't need. `archived_at` already exists on every archived task purely for filtering, and it doubles as a clean, deterministic sort key with no new storage: most-recently-archived first (or oldest-first, your call), with task `id` as a tiebreaker for same-timestamp archives. This also fits naturally into the `--sort` vocabulary you already have on `tasks`/`search` — worth adding `archived-at` as a recognized sort value there for consistency, and having the archived section default to it. Because it's a computed, sorted list rather than a stored sequence, it isn't manually reorderable — same as you can't drag-reorder `search` results today.

**Moving tasks out.** This is really two different operations worth separating:

Unarchiving is the common case — clearing `archived_at` makes the task reappear in whatever column it was already filed under (since it never actually left that column on disk). No destination picking needed; this is just the `a` unarchive action on a focused archived card.

Reassigning which column an archived task belongs to *without* unarchiving it is a rarer, separate operation — "file this under a different column for whenever it resurfaces." Move-mode's interaction model (adjacent-column stepping with arrow keys, dashed amber border) assumes the card lives inside the visible column layout, which the archived section deliberately doesn't — so `m` probably shouldn't try to reach into it. That case is better served by the existing update path (`e` edit, or `:update <task> --column <column>` in the command bar) with `archived_at` left untouched.

That raises a placement question: is the archived section meant to sit in the same `Tab`/arrow-key column-cycling flow as real columns (in which case move-mode reaching it is at least plausible), or is it a separate docked panel outside that flow (in which case move-mode clearly doesn't apply)? That decision resolves the move-mode question either way.

---

## User

I think I prefer having a dedicated column for archived tasks while keeping the archived_at field. i don't care if the task loses the column it was in, and archiving and unarchiving are as simple as moving a task from the column its in to the archive column, or back out. When visible the column behaves as every other column does. For the CLI and REPL, just list the archive column along with the others and all the move command to move a task into the archive column, at which time archived_at is also updated. For listing all tasks in a board, just skip the archive column

## Assistant

That resolves ordering for free — the archive column gets the same `[tasks] order` list every other column already has, so no new mechanism needed there. It also simplifies the TUI: toggling visibility becomes "render N-1 vs N columns," no synthetic aggregation or custom sort logic.

A few things this pivot leaves open, though:

`archived_at` becomes a derived value once column membership is the real signal — moving out of archive should presumably clear it back to `None`, since "moved out" and "unarchived" are now the same event. Worth confirming that's the intent, versus leaving it as a historical "last archived" timestamp that persists after unarchiving (in which case column membership, not the field, becomes the actual source of truth for "is this archived right now," and the field is just an audit trail).

The archive column needs to be reliably identifiable by the system — for skipping it in listings, dimming/hiding it in the TUI, etc. Since columns are otherwise fully user-editable (`column rename`, `column delete`, `column create`), what stops someone from renaming it, deleting it, or creating a second column also called "archive"? Either the slug `archive` is reserved and exempted from normal column mutation commands, or the board's `.metadata` records which column slug currently serves as the archive column so it can be renamed like any other.

Related: is the archive column always present (created automatically alongside `todo`/`in-progress`/etc. at `board create`), or created lazily the first time a task is moved into it?

Does board-wide `search` (unscoped by board) also skip archive columns by default the way `task list <board>` now does, with `--archived` bringing them back in? That was the earlier plan and I'd assume it still holds, but worth confirming since search doesn't have a natural column-scoping the way `task list <board>/archive` does.

And with `task list <board>/archive` now just working like addressing any other column, is a separate `--archived` flag on `task list` still needed, or does it collapse into redundant syntax for the same thing?

Board-level archiving is unaffected by any of this — still the `.metadata` flag approach from earlier, since a board can't be "moved into a column." Just confirming that stays as-is.

---

## User

1) reset archived_at when moving out of the archive column
2) add a metadata field to identify a column as the archive column
3) lazily create the archive column
4) unscoped board wide search skips the archive column by default. --archived shows only the archived items
5) remove the --archived flag from task list

## Assistant

Locks in cleanly, with two consequences worth flagging.

First: `move <task> archive` and `move <task> <column>` now fully cover archiving/unarchiving a task — that's the same operation as the `kanban task archive`/`unarchive` and REPL `archive <task>`/`unarchive <task>` commands we designed earlier. Do those still exist as dedicated verbs (thin wrappers around `move`, kept for discoverability/readability), or do they go away entirely for tasks now that `move` does the job, leaving `archive`/`unarchive` as board-only commands (since boards have no move equivalent)?

Second: since a task loses the record of its prior column when archived, unarchiving no longer has an implicit destination — it's a normal move requiring the user to pick a column, not a symmetric "undo." That changes the TUI shortcut discussion from before: `a` on an active card can stay a fast single-key action (fixed destination: archive), but there's no equivalent single-key "unarchive" since the destination is ambiguous — restoring a card from the archive column is really just using `m` move-mode like any other cross-column move, not a toggle.

---

## User

1) let's remove the archive/unarchive commands. 2) that's fine

## Assistant

Design is settled. Full picture:

**Storage.** Task frontmatter keeps `archived_at`, set on move into the archive column, cleared on move out. The archive column is identified by a metadata field (not a reserved slug, so it can be renamed), created lazily on first archive. Board archiving stays independent — a `.metadata` flag, unaffected by any of this.

**CLI**
```
kanban column list <board>                          # includes archive column
kanban task list <board>[/<column>]                 # unscoped skips archive column; /archive shows it
kanban task move <board>/<column>/<task> archive     # archives
kanban task move <board>/archive/<task> <column>     # unarchives
kanban search <query> [--board <board>] [...filters] [--archived]   # skips archive column by default; --archived = only archived
kanban board list [--archived]
kanban board archive <board>
kanban board unarchive <board>
```

**REPL** mirrors it: `tasks` unscoped skips the archive column, `tasks archive` shows it; `mv <task> archive` / `mv <task> <column>` archive and unarchive tasks; `search --archived`; `boards [--archived]`; `archive --board` / `unarchive --board` remain, board-only now.

**TUI.** Archive column is real, hidden by default, toggled with a dedicated key, behaves like any other column when shown. `a` on a focused card quick-archives it. No single-key unarchive — restoring a card is a normal move-mode operation since there's no remembered destination. Board archive/unarchive lives in the command palette.

Ready for implementation whenever you want to move on it.

---

## User

A small update. Let's have search commands include archived tasks. No additional flag to distinguish. The user can exclude archived tasks with the --exclude flag.

## Assistant

Updated:

```
kanban search <query>
    [--board <board>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by>|<column>]
    [--reverse]
    [--exclude <column>]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]
```

Same for the REPL `search` verb — drop `--archived`, add `--exclude <column>`. Default search results span every column, archive included; `--exclude archive` drops it, same as excluding any other column.

Worth flagging: this makes `search` inclusive-by-default while `task list <board>` (unscoped) stays exclusive-by-default — you still need `task list <board>/archive` to see archived tasks there, but `search` shows them unprompted. That's a real asymmetry between the two commands, and a reversal of the original principle that archived items shouldn't appear in searches unless asked for. Sounds like it's deliberate given you've said it twice — just confirming that's the intent rather than an oversight.

---

## User

that is the intent

## Assistant

Good — that's the final state, then. Ready whenever you want to move to implementation.

---

## User

A small update. Let's have search commands include archived tasks. No additional flag to distinguish. The user can exclude archived tasks with the --exclude flag.
A small update. Let's have search commands include archived tasks. No additional flag to distinguish. The user can exclude archived tasks with the --exclude flag.

## Assistant

*(duplicate message — see prior turn)*

---

## User

Actually why don't we just remove the archived_at property from the task entirely. We can tell when a task was archived by inspecting the git history

## Assistant

Makes sense — column membership already fully determines archived status, so `archived_at` was really just carrying "when," and that's exactly what git history is for. Dropping it also removes the risk we already flagged: a field that has to be kept in sync with column membership by every move operation, with no real independent value once history exists elsewhere.

Two things worth being aware of:

`updated_at` likely already approximates "recently archived" for sorting purposes, since `move` presumably bumps it like any other mutation — so `--sort updated-at` gets you close to "most recently archived first" without needing a dedicated field, with the caveat that it's imprecise if a task gets edited again after archiving.

For an exact archive timestamp you'd now go through `kanban log <task>` rather than a glanceable field on `task info` — a real but small cost, and consistent with treating git as the audit trail. One risk to flag: `kanban squash` exists specifically to collapse commits before pushing, so if a user squashes across an archive event, the fine-grained "moved to archive" commit could merge into something broader and the precise timestamp becomes harder to recover. Worth deciding if that's an acceptable tradeoff or if it's rare enough not to matter in practice.

---

## User

When listing all tasks for a board with `kanban task list <board>` or for the repl with `tasks`, by default the archived tasks are not include. I'd like to add an `--include-archived` flag to list all tasks

## Assistant

```
kanban task list <board>[/<column>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by|<column>>]
    [--reverse]
    [--exclude <column>]
    [--include-archived]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]
```

```
tasks [<column>]
    [--slugs]
    [--exclude <column>]
    [--include-archived]
    [--sort ...]
    [--reverse]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]
```

Two edge cases worth a quick ruling: `--include-archived --exclude archive` together are contradictory — I'd have `--exclude` win since it's the more explicit ask. And `--include-archived` is a no-op when scoped to a single non-archive column (`tasks todo --include-archived`), since archived tasks can't be there anyway — fine to just silently ignore rather than error.

---

## User

We'll raise an error if we include the flag with a column. I think we raise an error in the first case as well rather than assume intent

## Assistant

Both errors then: `--include-archived` combined with a column-scoped invocation (`tasks todo --include-archived` or `kanban task list <board>/todo --include-archived`) errors, and `--include-archived` combined with `--exclude` errors rather than silently picking a winner. Consistent, and matches the project's general stance of surfacing ambiguity instead of guessing at it.

---

## Final Design Summary

**Storage / data model**
- Tasks no longer carry an `archived_at` field. Archive status is determined solely by column membership.
- The archive column is identified via a metadata field (not a reserved slug), so it can be renamed like any other column.
- The archive column is created lazily, the first time a task is moved into it.
- Board-level archiving is independent: a boolean flag in the board's `.metadata`, unaffected by the task-level mechanism.
- "When was this archived" is answered via git history (`kanban log <task>`), not a stored field. `updated_at` gives an approximate signal for sorting. `kanban squash` can reduce the precision of that history.

**CLI**
```
kanban column list <board>                          # includes archive column
kanban task list <board>[/<column>]
    [--sort <title|priority|due-date|created-at|updated-at|created-by|<column>>]
    [--reverse]
    [--exclude <column>]
    [--include-archived]                             # errors if combined with a column or with --exclude
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban task move <board>/<column>/<task> archive     # archives
kanban task move <board>/archive/<task> <column>     # unarchives

kanban search <query>
    [--board <board>]
    [--sort ...]
    [--reverse]
    [--exclude <column>]                             # search includes archived by default; exclude to hide
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

kanban board list [--archived]
kanban board archive <board>
kanban board unarchive <board>
```

**REPL**
```
boards [--slugs] [--archived]

tasks [<column>]
    [--slugs]
    [--exclude <column>]
    [--include-archived]                             # errors if combined with a column or with --exclude
    [--sort ...]
    [--reverse]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

mv <task> archive       # archives
mv <task> <column>      # unarchives

search <query>
    [--slugs]
    [--board <board>]
    [--sort ...]
    [--reverse]
    [--exclude <column>]
    [--assigned-to <name>]
    [--priority <low|medium|high>]
    [--tag <tag>]
    [--due-before <date>]
    [--due-after <date>]
    [--created-by <name>]

archive --board          # archives the active board
unarchive --board        # unarchives the active board
```

No dedicated `archive`/`unarchive` commands for tasks — `move`/`mv` covers it.

**TUI**
- The archive column is a real column, hidden by default, toggled with a dedicated key (`A`), behaves like any other column when shown.
- `a` on a focused card quick-archives it (fixed destination).
- No single-key unarchive — restoring a card uses normal move-mode (`m`), since there's no remembered prior column.
- Board archive/unarchive lives in the command palette, not a hotkey.
