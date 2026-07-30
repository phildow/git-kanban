# Git Options

Date: 20260630_211209

ID: 2abd6498-01ca-4cc6-9acd-0e21f7e67a02


**User**: [2026-06-14 10:23:36]

Git is an integral part of the project and is used for change mangement. Describe git hooks and how they might be helpful here

---


**Claude**: [2026-06-14 10:24:06]

 ## Git Hooks for the Kanban System

Git hooks are scripts that run automatically at specific points in git's execution. For this project, they serve two main purposes: **keeping the index in sync** and **enforcing structural integrity**. Here's where each hook fits into the architecture.

---

### Pre-commit

**Purpose:** Validate and normalize before a commit is recorded.

This is the most valuable hook for this project. Since the CLI auto-commits after every operation, the pre-commit hook acts as a last line of defense — catching anything that slipped through domain validation or that was written directly to the filesystem outside the application.

What it should do:

- **Validate frontmatter** on every `.md` file in the staging area. Reject commits where a task file is missing a required field (`id`, `title`, `created_at`) or has a malformed UUID.
- **Detect duplicate UUIDs** across all staged task files. Two tasks with the same `id` would silently corrupt the index.
- **Enforce filename/title consistency.** The task's `title` field in frontmatter must match the filename (minus the `.md` extension). This is a core invariant of the system and the hook is the right place to enforce it when files are edited externally.
- **Normalize `updated_at`.** If a task file is being modified, stamp it with the current UTC timestamp before it lands in the commit. This keeps the field accurate even when users edit files directly in their editor via `kanban task edit`.

---

### Commit-msg

**Purpose:** Enforce structured commit message format.

The facade is responsible for composing structured commit messages (e.g. `task(create): "Fix login bug" [a3f9c2d1]`). The commit-msg hook validates that every commit — whether from the CLI or a manual `git commit` — conforms to that schema.

This matters for `kanban log`, which parses commit history to reconstruct a task's audit trail. If a rogue commit uses a free-form message, the log command either silently skips it or errors — neither is good.

The hook rejects commits whose messages don't match the expected pattern, or that are missing the UUID anchor where one is required.

---

### Post-commit

**Purpose:** Keep the index current after every commit.

After the CLI commits a change, the index needs to reflect it. Rather than having the facade call `IndexService.sync()` explicitly (which couples the facade to index timing), the post-commit hook handles it declaratively.

What it does: inspects the files changed in `HEAD` and calls a lightweight `kanban index update --files <paths>` command (or directly invokes the index update logic) to re-parse only the affected markdown files and upsert their records into `.index.db`.

This is particularly important for the external-edit detection case: if a user edits a task file and then commits manually with `git commit`, the post-commit hook ensures the index catches up without requiring a full `kanban index rebuild`.

---

### Post-merge and Post-rewrite

**Purpose:** Rebuild or patch the index after history changes.

`post-merge` fires after a `git pull` or `git merge`. `post-rewrite` fires after `git rebase` or `git commit --amend`. Both can bring in task files the index has never seen, delete tasks the index still references, or change file content the index has cached.

Both hooks should trigger a **selective index sync** against the changed file list. For large boards, a full rebuild on every pull is too slow; diffing `ORIG_HEAD..HEAD` (or the rewrite map passed to `post-rewrite`) gives the exact set of files to re-examine.

This is also where **conflict detection** lives: if a merge produces a `.md` file with git conflict markers, the hook flags it immediately rather than letting the index ingest corrupted frontmatter.

---

### Pre-push

**Purpose:** Final integrity check before sharing history.

Before any `git push`, validate that the repository is in a consistent state: no orphaned task files (a `.md` file exists but its UUID isn't in the index), no broken `.order` files referencing columns or tasks that don't exist.

This is also the natural place to remind the user to run `kanban squash` if the outgoing commit count exceeds a threshold — or even to block the push and require it, depending on team preference.

---

### Hook Installation

Since git hooks aren't versioned in `.git/hooks` by default, `kanban init` should:

1. Write the hooks into a versioned directory, e.g. `.kanban/hooks/`
2. Run `git config core.hooksPath .kanban/hooks` to point git at them
3. Make each hook executable (`chmod +x`)

This way hooks are part of the repository and anyone who clones it gets them automatically after running `kanban init`. The hooks themselves should be thin shell scripts that delegate to `python -m kanban hooks <hook-name>` so all real logic stays in Python and is testable.

---

### Summary Table

| Hook | Trigger | Role in this system |
|---|---|---|
| `pre-commit` | Before commit is recorded | Validate frontmatter, detect duplicate UUIDs, enforce filename/title consistency, normalize `updated_at` |
| `commit-msg` | After message is written | Enforce structured message schema needed by `kanban log` |
| `post-commit` | After commit succeeds | Sync index for changed files |
| `post-merge` | After merge/pull | Selective index sync, conflict detection |
| `post-rewrite` | After rebase/amend | Same as post-merge |
| `pre-push` | Before push | Structural integrity check, optional squash reminder |

---


**User**: [2026-06-14 18:10:27]

i'd like these hooks to work with a git repository that  also manages other files in addition to the kanban tasks. What adjustments are needed to accommodate that behavior?

---


**Claude**: [2026-06-14 18:10:56]

 ## Accommodating a Mixed-Content Repository

The core adjustment is simple: **every hook must scope itself to the kanban subtree**. A hook that fires on any commit will interfere with commits that have nothing to do with kanban tasks. The changes fall into a few categories.

---

### Path Scoping in Every Hook

Each hook needs to filter the files it examines down to those under the kanban root (wherever `.kanban/` lives). Rather than operating on all staged or changed files, every hook opens with something like:

```python
KANBAN_ROOT = ".kanban/boards"

def get_kanban_files(file_list):
    return [f for f in file_list if f.startswith(KANBAN_ROOT) and f.endswith(".md")]
```

If after filtering that list is empty, the hook exits immediately with success — it has nothing to say about a commit that only touches, say, `src/` or `README.md`. This is the most important change: **hooks must be silent and non-blocking for non-kanban commits**.

---

### Hook-by-Hook Adjustments

**pre-commit**

Currently assumes all staged `.md` files are task files. In a mixed repo, `.md` files in `docs/` or `README.md` must be ignored. Scope the staged file scan to `KANBAN_ROOT` only. The hook becomes a no-op for commits that touch only non-kanban files.

**commit-msg**

This is the trickiest hook to adjust. Currently it rejects any commit message that doesn't conform to the kanban schema — but most commits in a mixed repo are ordinary development commits and shouldn't be forced into `task(create): "Fix login bug" [a3f9c2d1]` format.

The solution is to make the structured message format **opt-in via detection rather than mandatory**. The hook inspects the staged files (accessible via `git diff --cached --name-only` even from the commit-msg hook by shelling out). If the commit touches kanban files, it validates the message. If it doesn't, it passes unconditionally. 

Alternatively, add a lightweight convention: kanban-generated commits are prefixed with `kanban:` and the hook only validates messages that carry that prefix. Human commits are never touched.

**post-commit**

Least affected. It already diffs `HEAD` to find changed files — just filter that list to `KANBAN_ROOT` before passing to the index updater. If no kanban files changed, skip index sync entirely.

**post-merge and post-rewrite**

Same pattern. Diff the changed file set, filter to kanban paths, sync only those. The conflict-marker detection should similarly scope to kanban `.md` files only — conflict markers in a source file are the developer's business, not the kanban hook's.

**pre-push**

The orphan-task and broken-`.order` checks are already scoped to `.kanban/` implicitly, so these need the least adjustment. The squash reminder needs one addition: only fire if the outgoing commits include at least one kanban commit (detectable by the `kanban:` prefix convention, or by checking whether any outgoing commit touches `KANBAN_ROOT`).

---

### Configuring the Kanban Root

In a mixed repo the `.kanban/` directory might not be at the repository root. `kanban init` should write the resolved path into `.kanban/.config`:

```toml
[repository]
kanban_root = "project/planning/.kanban"   # relative to git root
```

Every hook reads this value at startup so path scoping works regardless of where the kanban tree lives within the repo.

---

### Communicating Intent on Kanban Commits

When the facade auto-commits after an operation, it should stage **only the kanban files involved in that operation** rather than doing a blanket `git add .`. This keeps kanban commits clean and ensures the pre-commit and commit-msg hooks see a homogeneous staging area when validating a kanban operation. It also means a developer with unrelated staged changes won't have them accidentally swept into a kanban commit.

```python
# In GitService — stage only the specific paths involved
repo.index.add(kanban_file_paths)
repo.index.write()
```

If the user has unrelated staged changes when a kanban operation runs, the facade should either stash them before committing and restore them after, or use `git commit` with explicit `--only <paths>` targeting to avoid disturbing the developer's working state.

---

### Summary of Adjustments

| Hook | Adjustment |
|---|---|
| `pre-commit` | Filter staged files to `KANBAN_ROOT/*.md` before any validation; exit 0 immediately if none |
| `commit-msg` | Validate schema only when staged files include kanban paths, or only when message carries `kanban:` prefix |
| `post-commit` | Filter `HEAD` diff to kanban paths before index sync; skip if none |
| `post-merge` / `post-rewrite` | Filter changed file set to kanban paths; skip conflict detection for non-kanban files |
| `pre-push` | Scope orphan/order checks to `.kanban/`; only fire squash reminder if outgoing commits include kanban changes |
| `GitService` | Stage only operation-specific kanban paths; stash or use `--only` to avoid capturing unrelated staged changes |

---


**User**: [2026-06-14 19:14:59]

I originally thought a kanban project would be initialized in a pre-existing git repository and mix its  change management with that of the parent repository, but an alternative is to treat kanban like a git submodule with its own commit history. What are the pros and cons of each approach?

---


**Claude**: [2026-06-14 19:15:36]

 ## Shared Repository vs. Submodule

This is fundamentally a question about who owns the git history and what that history is *for*. The two approaches have genuinely different characters.

---

### Shared Repository (Original Approach)

Kanban commits live alongside code commits in the same history.

**Pros**

- **Zero setup friction.** `kanban init` in an existing repo just writes `.kanban/` and configures hooks. No submodule registration, no nested clone, no `.gitmodules`.
- **Unified history.** You can see in a single `git log` that a task was moved to "done" in the same week a feature branch was merged. That correlation can be genuinely useful for retrospectives or audits.
- **Simpler mental model for solo users or small teams.** One repo, one remote, one push.
- **`kanban log` for a task can cross-reference nearby code commits** if you ever want to build that feature — the information is all in one graph.

**Cons**

- **History pollution.** A busy board generates a lot of commits. `git log` for code review purposes becomes noisy. `git bisect` and blame workflows get harder to reason about. Even with `kanban squash`, the noise exists between squashes.
- **Hook complexity** — as just discussed. Every hook must carefully scope itself to avoid interfering with code commits, and vice versa. That complexity is load-bearing; a mistake breaks developer workflows.
- **Merge conflicts bleed across concerns.** A rebase or merge gone wrong can produce conflicts in both source files and kanban markdown simultaneously, which are conceptually unrelated problems to untangle at the same time.
- **The kanban state is coupled to the code branch.** If you're on a feature branch, `git checkout main` changes your board state too — your "in-progress" tasks disappear and reappear depending on which branch you're on. This is almost never what you want from a project management tool.
- **Access control is all-or-nothing.** Anyone with read access to the repo sees the board. Anyone with write access can modify tasks. You can't give a project manager board access without giving them code access.

---

### Submodule (Alternative Approach)

The `.kanban/` directory is a separate git repository, registered as a submodule of the parent.

**Pros**

- **Histories are cleanly separated.** `git log` in the parent repo shows only code changes. The kanban repo has its own history that only board operations appear in. Both are legible on their own terms.
- **Branch independence.** Checking out a feature branch in the parent repo doesn't change the board state. The submodule is pinned to a commit, but you can detach that pin and let the kanban repo float on its own branch — effectively making board state independent of code branch.
- **Access control becomes possible.** The kanban repo can live at a different remote with different permissions. A PM can have write access to the board repo without touching the code repo at all.
- **Hook isolation.** Hooks in the parent repo never need to know about kanban files. Hooks in the kanban repo can assume every file they see is a kanban file. The scoping problem disappears.
- **Portable boards.** A board isn't inherently tied to one codebase. You could attach the same kanban repo to multiple projects, or detach it and reattach it elsewhere.

**Cons**

- **Submodules are notoriously awkward.** They require `git submodule update --init` after cloning, they produce detached HEAD states that confuse people, and `git pull` in the parent doesn't automatically update them. These are well-known paper cuts that create real friction for teams who aren't already comfortable with submodules.
- **Two commits for every operation.** A task move requires a commit in the kanban submodule *and* a commit in the parent repo to update the submodule pointer. The `kanban squash` workflow becomes more complex — you'd need to squash in both repos and keep the pointer updates coherent.
- **`kanban init` is more invasive.** You're asking someone to add a submodule to their repo, which modifies `.gitmodules` and creates a registered nested repo. That's a bigger ask than writing a `.kanban/` directory.
- **Tooling assumptions break.** GitHub, GitLab, and most CI systems handle submodules as second-class citizens. PR diffs, code search, and Actions/Pipelines all require extra configuration to handle them correctly.
- **The correlation value is lost.** If cross-referencing task history with code history is something you want, a submodule makes that harder — you're querying two separate graphs.

---

### A Third Path: Orphan Branch

Worth naming because it addresses the core tension directly. An orphan branch (`git checkout --orphan kanban`) lives in the same repository but has a completely independent commit history — no shared ancestors with `main` or any code branch. Board state lives on this branch, code lives on the others, and they never intersect in `git log` or merges.

**This captures most of the submodule benefits without the submodule machinery:**
- Clean history separation
- No hook scoping complexity
- Branch independence from code
- Single remote, single clone

**The tradeoffs:** it's an unconventional git usage that most developers haven't encountered, tooling (GitHub PR views, etc.) doesn't surface orphan branches prominently, and you need a checkout or `git show kanban:<path>` dance to read board files from a code branch context — which complicates the CLI since it can't just use the filesystem directly.

---

### How to Decide

| Factor | Shared Repo | Submodule | Orphan Branch |
|---|---|---|---|
| Solo or small dev team | Best fit | Overkill | Reasonable |
| Mixed technical/non-technical stakeholders | Poor | Good | Poor |
| Board must be branch-independent | Problematic | Good | Good |
| Minimal setup friction | Best | Worst | Middle |
| Clean `git log` for code review | Poor | Good | Good |
| Hook simplicity | Poor | Good | Good |

For a tool targeting developers in a single-team context, the **shared repo** approach is probably the right default — it's the path of least resistance and the history coupling is a manageable annoyance rather than a real problem. The **orphan branch** is worth offering as an opt-in (`kanban init --isolated`) for teams that care about log cleanliness without wanting submodule complexity. The submodule approach is hard to recommend as a default given its usability costs, though it becomes compelling if cross-team access control is a real requirement.

---


**User**: [2026-06-14 19:24:20]

Tell me more about orphan branches in git

---


**Claude**: [2026-06-14 19:24:56]

 ## Orphan Branches in Git

An orphan branch is a branch with no parent commit — it starts a completely fresh commit history within an existing repository. The repository itself is the same (same `.git` directory, same remotes, same object store), but the orphan branch's commits form a graph that shares no ancestors with any other branch.

---

### How They're Created

```bash
git checkout --orphan kanban
```

After this command, you're on a branch called `kanban` with no commits. Git puts you in an unusual state: the working tree still contains whatever files were there before (inherited from your previous branch), but none of them are committed — they're all staged as new files. You typically clear that immediately:

```bash
git rm -rf .          # clear the inherited working tree
# now create your initial structure
mkdir -p .kanban/boards
git add .kanban/
git commit -m "kanban: initialize board"
```

At this point `kanban` has exactly one commit and zero connection to `main`'s history.

---

### How the Object Store Works

This is the key insight. Git stores everything — commits, trees, blobs — as content-addressed objects in `.git/objects`. Branches are just pointers (refs) into that object graph. An orphan branch's commits are objects in the same store as all the code commits, but they form a disconnected subgraph.

```
main:    A --- B --- C --- D
                           
kanban:  X --- Y --- Z
```

`A` through `D` and `X` through `Z` are all objects in the same `.git/objects` directory. `git log main` traverses one graph. `git log kanban` traverses the other. They never meet. `git gc` won't collect orphan commits as long as the branch ref exists pointing to them.

This is exactly how GitHub Pages works — `gh-pages` is conventionally an orphan branch holding only static site files, completely separate from the source code history. It's a well-established pattern, just not widely understood outside that context.

---

### Reading Files Across Branches Without Checkout

Because both branches share the object store, you can read kanban files from the code branch context without checking out:

```bash
git show kanban:.kanban/boards/my-project/todo/fix-login-bug.md
```

And list the kanban tree:

```bash
git ls-tree -r kanban --name-only
```

For the CLI this matters: the application can read board state directly from the kanban branch's git objects without ever switching branches. This is how `pygit2` would access it:

```python
repo = pygit2.Repository(".")
kanban_branch = repo.branches["kanban"]
kanban_commit = kanban_branch.peel(pygit2.Commit)
tree = kanban_commit.peel(pygit2.Tree)

# walk the tree to find task files
def find_entry(tree, path):
    parts = path.strip("/").split("/")
    current = tree
    for part in parts:
        current = current[part]
    return current
```

The alternative — and simpler approach for the CLI — is to just **keep the kanban branch checked out in a separate worktree**, which sidesteps the object-reading complexity entirely.

---

### Git Worktrees

`git worktree` is the natural companion to orphan branches for this use case. A worktree lets you check out a second branch into a separate directory while keeping your main working tree on its current branch:

```bash
git worktree add .kanban-worktree kanban
```

Now `.kanban-worktree/` is a live filesystem checkout of the `kanban` branch. The CLI reads and writes files there using normal filesystem operations. When it commits, it commits to the `kanban` branch without touching `main`. The developer never has to switch branches.

```
repo/
  src/           ← main branch, normal working tree
  .kanban-worktree/   ← kanban branch, separate worktree
    .kanban/
      boards/
```

`kanban init --isolated` could set this up automatically: create the orphan branch, add the worktree, write the path into a config file so the CLI knows where to find it.

---

### Merging and History

Orphan branches cannot be merged in the conventional sense — there's no common ancestor for git to use as a merge base. If you tried `git merge kanban` from `main`, git would refuse (or with `--allow-unrelated-histories`, produce a merge commit that uncomfortably unifies the two trees). 

This is a feature for this use case, not a bug. You *never want* kanban history merging into your code history. The separation is the point.

However, you can still `git push` an orphan branch to a remote:

```bash
git push origin kanban
```

The remote gains a new branch with its own disconnected history. Pull requests, branch protection rules, and access controls all work normally on it.

---

### Rebasing and Squashing

`git rebase` works within an orphan branch's own history — you can squash kanban commits against each other freely. The `kanban squash` command would run something like:

```bash
git rebase -i $(git rev-list --max-parents=0 kanban)
```

That `rev-list --max-parents=0` gives you the root commit of the orphan branch (the commit with no parents), which is the correct base for an interactive rebase of the entire history.

---

### What `git log` Looks Like

From `main`, the kanban branch is simply invisible:

```bash
git log --oneline          # shows only code commits
git log --oneline --all    # shows both graphs, clearly separated
git log --oneline kanban   # shows only kanban commits
```

With `--all` and `--graph` you'd see two parallel lines with no connecting edges — visually clean and honest about the separation.

---

### Failure Modes to Know About

**Accidental checkout.** If a developer runs `git checkout kanban` in the main working tree, they'll find a directory with only kanban files and no source code. This is confusing. Mitigating options: name the branch something less generic like `kanban/state`, document it clearly, or use the worktree approach so the branch is always checked out elsewhere and a direct checkout is less likely.

**Clone behavior.** `git clone` fetches all branches by default, but only checks out the default branch. A new team member who clones the repo needs to know to run `kanban init` (or `git worktree add`) to activate the kanban worktree. This is a one-time friction but worth documenting prominently.

**`git push --mirror` and forks.** Mirror pushes and some fork workflows copy all refs including the orphan branch to the destination. Usually harmless, but worth being aware of if the team uses those patterns.

---


**User**: [2026-06-14 19:45:33]

The worktree option sounds like the right one. Can we use the same `.kanban` folder that contains the kanban folders and files for the worktree directory, so initialize the worktree like `git worktree add .kanban kanban`

---


**Claude**: [2026-06-14 19:45:53]

 This is an appealing idea for cleanliness — the worktree lives exactly where the kanban data lives — but it runs into a fundamental git constraint.

### The Problem

When you run `git worktree add .kanban kanban`, git needs to write a `.git` file into `.kanban/` to link the worktree back to the main repository's `.git` directory. That file would look like:

```
gitdir: ../.git/worktrees/kanban
```

The issue is that `.kanban/` already exists as a regular directory created by `kanban init`. Git refuses to add a worktree into a non-empty directory — it requires the target to either not exist or be empty.

Even if you worked around that by creating the worktree first and then populating it, you'd have a `.git` file sitting inside your kanban data directory alongside `.config`, `boards/`, and `.index.db`. That file has to be there for the worktree to function, which means your kanban storage layer has to know to ignore it, your `.gitignore` logic gets complicated, and anything that scans the directory (like the index rebuilder) has to filter it out.

---

### The Deeper Issue

The worktree approach works cleanly precisely because the worktree directory and the kanban data directory are the same thing. But git's worktree mechanism owns the directory it's given — it expects to control what's in it. Mixing that with application-managed files creates two systems with overlapping jurisdiction over the same directory, which tends to produce subtle breakage over time.

There's also a timing problem during `kanban init`. The correct sequence would be:

1. Create the orphan branch with an initial commit containing the kanban structure
2. Add the worktree pointing at `.kanban/`

But step 2 requires `.kanban/` to be empty or absent, which means step 1 can't have written anything there yet — including the initial board structure that the first commit is supposed to contain. You'd need to build the initial commit using git plumbing commands against the object store directly, without ever touching the filesystem, which is significantly more complex than the straightforward init flow.

---

### The Clean Alternative

Keep the worktree one level removed and symlink or configure your way to cleanliness:

```bash
git worktree add .kanban-store kanban
```

Then in `.kanban/.config`, record the worktree path:

```toml
[repository]
worktree = ".kanban-store"
```

The CLI reads that config key and routes all filesystem operations to `.kanban-store/`. From the application's perspective the indirection is invisible — it's just a configured path. From the user's perspective, `kanban init` sets it all up and they never need to think about it.

If the separation between `.kanban/` (config, index) and `.kanban-store/` (boards, tasks) feels untidy, another clean split is:

```
.kanban/          ← regular directory, never a worktree
  .config         ← includes worktree path
  .index.db       ← cache, gitignored

.kanban-store/    ← git worktree checked out to `kanban` branch  
  boards/
  .order
  my-project/
    ...
```

This actually reflects a meaningful architectural truth: `.kanban/` contains local machine state (config, cache) that should probably never be committed at all, while `.kanban-store/` contains the shared board state that git is tracking. Separating them makes that distinction explicit rather than muddling them together.

---


**User**: [2026-06-14 19:56:31]

describe the worktree option in more detail. how does git coordinate the second branch in the worktree folder with the main branch? do they use the same commit history? how is the worktree branch kept in sync with the remote repository?

---


**Claude**: [2026-06-14 19:57:12]

 ## How Git Worktrees Work

A worktree is a checked-out working tree linked to an existing repository. The key thing to understand is that a git repository and a working tree are separate concepts that git normally presents as one thing — worktrees make that separation explicit.

---

### The `.git` Directory vs. The Working Tree

In a normal repository:

```
my-repo/
  .git/          ← the repository (all history, all objects, all refs)
  src/           ← the working tree (files you actually edit)
  README.md
```

The `.git` directory *is* the repository. The files alongside it are just one possible view of it — the checked-out working tree. Everything git knows about your project lives in `.git`. The files outside it are transient; you could delete them all and `git checkout` would restore them.

A worktree adds a second working tree, linked to the same `.git` directory:

```
my-repo/
  .git/
    worktrees/
      kanban/          ← metadata about the second worktree
        gitdir         ← points back to .kanban-store/.git
        HEAD           ← tracks which commit this worktree is on
        index          ← staging area, separate per worktree
  src/
  README.md
  .kanban-store/       ← second working tree
    .git               ← a file (not a directory) pointing to .git/worktrees/kanban
    boards/
    .order
```

The `.git` inside `.kanban-store/` is a plain text file containing one line:

```
gitdir: ../.git/worktrees/kanban
```

This is what links the worktree back to the main repository's object store. Git follows this pointer whenever it needs to read or write repository data from within the worktree.

---

### One Object Store, Two Working Trees

Both working trees share the exact same object store — the same `.git/objects` directory. Every commit, tree, and blob ever created in either working tree is stored there. There is no duplication.

What each worktree has independently is:

- **Its own `HEAD`** — tracking which commit it currently has checked out
- **Its own index** — the staging area for the next commit
- **Its own working tree files** — the actual files on disk

So from git's perspective, running `git status` in `my-repo/` asks "what differs between `my-repo/`'s index and `my-repo/`'s HEAD?" and running `git status` in `.kanban-store/` asks the same question but using `.kanban-store/`'s index and its HEAD. They answer independently using the same underlying object data.

---

### Branch Coordination and Exclusivity

Git enforces one rule above all others with worktrees: **the same branch cannot be checked out in two worktrees simultaneously**. If `main` is checked out in the primary worktree, you cannot check out `main` in `.kanban-store/`. Git will refuse with an error.

This is enforced via lock files in `.git/worktrees/<name>/`. When a worktree checks out a branch, it registers that branch as in-use. The `kanban` branch, checked out in `.kanban-store/`, is effectively reserved for that worktree. Nobody can accidentally check it out elsewhere.

The two branches — `main` in the primary worktree and `kanban` in `.kanban-store/` — are completely independent in terms of history, as described earlier. They don't share commits, they don't share a merge base, they don't affect each other at all. A commit made in `.kanban-store/` advances the `kanban` branch pointer. A commit made in `my-repo/` advances the `main` branch pointer. Neither knows about the other.

---

### What Happens During Normal Git Operations

**`git status`** in `my-repo/` — sees only the primary working tree. `.kanban-store/` appears as an untracked directory (or is gitignored). The kanban branch and its contents are invisible to this command.

**`git log`** in `my-repo/` — shows only `main`'s history by default. `git log --all` would show both graphs side by side, but with no connecting edges.

**`git commit`** in `my-repo/` — commits to `main`. Has no effect on the kanban branch.

**`git commit`** in `.kanban-store/` — commits to `kanban`. Has no effect on `main`. Uses the same underlying `git commit` machinery but with the worktree's own HEAD and index.

**`git add`** in `.kanban-store/` — stages to `.kanban-store/`'s own index file. Completely separate staging area from the primary working tree.

**`git checkout some-branch`** in `.kanban-store/` — switches `.kanban-store/` to a different branch (as long as it isn't already checked out elsewhere). The `kanban` branch is abandoned by that worktree, and the new branch is checked out into `.kanban-store/`'s files.

---

### Keeping the Worktree Branch in Sync With the Remote

This is where worktrees need the most explicit attention — there's no automatic synchronization. The `kanban` branch in `.kanban-store/` is just a local branch like any other, and it needs to be pushed and pulled manually (or by the application).

**Setting up the remote tracking relationship** happens once during `kanban init`:

```bash
# from within .kanban-store/
git push --set-upstream origin kanban
```

After this, `origin/kanban` is the remote tracking branch. From that point on, the sync operations work exactly as they do for any branch:

```bash
# push local kanban commits to remote
git -C .kanban-store push

# pull remote kanban commits down
git -C .kanban-store pull
```

The `git -C .kanban-store` flag tells git to operate as if it were run from inside that directory, which is how the CLI would invoke these operations without needing to change directories.

**What the application should do** is surface push and pull as explicit kanban operations rather than relying on users to remember to run them. The `KanbanService` facade would call `GitService.push()` and `GitService.pull()` at appropriate moments — probably not after every single commit (too slow and requires connectivity), but as explicit user actions or on a configurable schedule.

A reasonable default behavior:

```
kanban sync          # explicit pull then push
kanban push          # push only  
kanban pull          # pull only, with conflict detection
```

And `git push` in the primary working tree wouldn't touch the kanban branch at all — the developer would need `kanban push` or a separate `git -C .kanban-store push` to share board changes.

---

### Cloning and Team Setup

When a teammate clones the repository, they get all branches including `kanban`, but no worktree is set up automatically. The kanban branch exists as a remote tracking ref (`origin/kanban`) but has no local checkout.

`kanban init` on their machine needs to handle this case:

```python
def init(repo_path):
    repo = pygit2.Repository(repo_path)
    
    if "origin/kanban" in repo.branches.remote:
        # branch exists on remote — check it out into the worktree
        repo.create_branch("kanban", repo.branches.remote["origin/kanban"].peel())
        subprocess.run(["git", "worktree", "add", ".kanban-store", "kanban"])
    else:
        # first time — create the orphan branch and push it
        _create_orphan_branch(repo)
        subprocess.run(["git", "worktree", "add", ".kanban-store", "kanban"])
        subprocess.run(["git", "-C", ".kanban-store", "push", "--set-upstream", "origin", "kanban"])
```

From that point the teammate's setup is identical to the original developer's. Their `.kanban-store/` worktree tracks `origin/kanban`, and `kanban sync` keeps them current with the team's board state.

---

### The Full Picture

```
Remote (origin)
  origin/main     ← code history
  origin/kanban   ← board history

Local .git/
  objects/        ← all commits from both branches live here
  refs/heads/main
  refs/heads/kanban
  worktrees/
    kanban/
      HEAD        ← points to refs/heads/kanban
      index       ← kanban staging area

Primary worktree (my-repo/)
  HEAD → main
  src/, README.md ...

Kanban worktree (.kanban-store/)
  .git            → file pointing to ../.git/worktrees/kanban
  HEAD → kanban
  boards/, .order ...
```

The two branches are genuinely independent histories sharing one object store and one remote connection. The worktree mechanism is just git's way of making two branches simultaneously accessible on the filesystem without requiring branch switching.

---


**User**: [2026-06-15 19:43:38]

How doe we handle multiple users making commits to the kanban store? Can we manage this transparently and without branching?

---


**Claude**: [2026-06-15 19:44:22]

 ## Multi-User Sync on a Single Branch

The goal is linear history on `kanban` — no merge commits, no feature branches, just a clean sequence of task operations. This is achievable, but it requires accepting one fundamental constraint: **the last writer wins a rebase, not a merge**.

---

### The Core Pattern: Rebase on Pull

The standard git approach for linear history with multiple contributors is `pull --rebase`. Instead of creating a merge commit when local and remote histories diverge, it replays your local commits on top of whatever the remote has:

```
Before pull:
  remote: A → B → C → D    (D is someone else's commit)
  local:  A → B → C → E    (E is your commit)

After git pull --rebase:
  local:  A → B → C → D → E'   (E replayed on top of D)
```

The result is a linear history. `E'` is a new commit object — same changes as `E`, different parent — but the content is identical assuming no conflicts.

For the kanban application, this means:

```python
def sync(self):
    self._pull_rebase()   # fast-forward or rebase local commits on top of remote
    self._push()          # should now fast-forward cleanly
```

`kanban push` becomes a two-step operation internally: always pull-rebase first, then push. This is the same pattern `git pull --rebase && git push` represents at the command line.

---

### Conflict Likelihood Is Low

Markdown frontmatter conflicts are much rarer than code conflicts for a structural reason: **each task is its own file**. Two users editing the same line of the same source file is common. Two users editing the same task's frontmatter simultaneously is uncommon.

The operations most likely to produce a conflict:

- **Same task moved by two users** — both write to the same `.md` file, changing its directory path (a delete + add in git's view) and its `updated_at` field
- **Same task edited by two users** — both modify the same file's frontmatter
- **`.order` files** — these are the highest-conflict surface, since any column reorder or task add/move appends to or rearranges a shared file

Operations that never conflict:

- Creating different tasks (different files)
- Moving different tasks (different files)
- Working on different boards entirely

In practice, most kanban operations touch different files, making auto-rebase transparent most of the time.

---

### When Conflicts Do Occur

A rebase conflict on a kanban file means two users made incompatible changes to the same file. Git will pause the rebase and mark the file with conflict markers:

```
<<<<<<< HEAD
status: in-progress
updated_at: 2026-06-15T10:30:00Z
=======
status: done
updated_at: 2026-06-15T10:45:00Z
>>>>>>> E' (task: move "Fix login bug" to done)
```

The application has a few options for handling this, roughly in order of increasing complexity:

**Option 1: Surface the conflict and ask the user to resolve it**

The simplest approach. `kanban sync` fails with a clear message:

```
Sync conflict: "Fix login bug" was modified by alice and bob simultaneously.
  alice: moved to done       (10:45)
  bob:   moved to in-progress (10:30)

Run `kanban resolve` to choose a version, or edit .kanban-store/... directly.
```

The user runs `kanban resolve <task>` which opens the conflicted file in their editor (or presents a TUI choice), they pick a version, and `kanban sync --continue` completes the rebase.

**Option 2: Apply a deterministic resolution strategy automatically**

For specific field conflicts, the application can resolve automatically without user input:

- **`updated_at` conflicts**: always take the later timestamp — unambiguously correct
- **`status`/location conflicts**: "last write wins" by timestamp — take whichever `updated_at` is newer
- **`assignee`, `priority`, `tags` conflicts**: last write wins by timestamp

This covers the majority of real-world conflicts. The application inspects the conflict markers, parses both versions, applies the strategy, writes the resolved file, and continues the rebase — all transparently.

**Option 3: Semantic merge driver**

Git allows registering a custom merge driver per file pattern in `.gitattributes`:

```
.kanban-store/boards/**/*.md merge=kanban-task
```

And in `.git/config`:

```
[merge "kanban-task"]
    name = Kanban task merge driver
    driver = kanban merge-driver %O %A %B %L
```

Git calls the driver with the three versions (base, ours, theirs) as file paths. The driver resolves them and writes the result. This hooks directly into git's merge machinery, so it applies automatically during both rebase and merge operations without the application needing to detect or handle conflict markers explicitly.

This is the most transparent option but also the most complex to implement correctly. It's a good target state once the data model is stable.

---

### `.order` File Conflicts

These deserve special attention because they're the most likely conflict surface. An `.order` file might look like:

```
fix-login-bug
write-api-docs
add-rate-limiting
```

If alice adds `deploy-staging` and bob adds `rotate-keys` simultaneously, git sees two edits to the same file and conflicts them. The correct resolution is to include both entries — but in what order?

A custom merge driver for `.order` files can handle this by treating the file as an ordered set and applying a three-way merge that preserves both additions:

```
.kanban-store/**/.order merge=kanban-order
```

The driver takes the base version, alice's version, and bob's version, computes the diff of additions and removals against the base for each, and applies both sets of changes. Ordering ambiguity for simultaneous additions can be resolved by appending in a deterministic order (e.g. alphabetical, or by commit timestamp).

---

### Push Races

There's a window between pull-rebase and push where another user could push first, causing your push to be rejected:

```
1. alice: pull-rebase succeeds, history is now A→B→C→D→E'
2. bob:   pushes F before alice pushes
3. alice: push rejected — remote has moved to F
```

The solution is a retry loop:

```python
def sync(self, max_retries=3):
    for attempt in range(max_retries):
        self._pull_rebase()
        try:
            self._push()
            return
        except PushRejected:
            if attempt == max_retries - 1:
                raise SyncFailed("could not sync after retries — try again")
            continue
```

In practice, the window is milliseconds and retries succeed immediately. This is the same pattern used by most git hosting services' web editors.

---

### Auto-Sync Behavior

A few trigger points where the application should sync transparently:

| Trigger | Action |
|---|---|
| `kanban push` / `kanban pull` | Explicit user-initiated sync |
| `kanban repl` startup | Pull only — ensure fresh state before interactive session |
| After every write operation | Optional, configurable — pull-rebase then push |
| `kanban status` | Pull only — show current remote state |

Auto-sync after every write is the most transparent but requires network connectivity and adds latency to every operation. Making it configurable (`sync: on-write | manual | on-exit`) lets users tune the behavior for their connectivity situation. The REPL is a natural place to sync on entry and offer to sync on exit.

---

### What Transparency Actually Requires

For sync to feel invisible to the user, three things need to be true:

1. **Conflicts are rare** — which the file-per-task structure largely ensures
2. **When conflicts occur, they're auto-resolvable** — which the timestamp-based strategy handles for most cases
3. **The retry loop handles push races** — which is straightforward to implement

The remaining case — two users making genuinely incompatible semantic decisions about the same task at the same time — can't be resolved without human judgment. That case should surface a clear, actionable message rather than a raw git conflict. The application owns the UX of conflict resolution; git is just the mechanism that detects it.

---


**User**: [2026-06-18 05:45:34]

when using a worktree does git keep the commit histories separate

---


**Claude**: [2026-06-18 05:45:47]

Yes — separate in the sense of forming distinct chains with no shared edges, but stored in the same underlying object database. It's worth being precise about what "separate" means here, because there are really two different questions bundled together.

### Same Object Store, Disconnected Graphs

Every commit, regardless of which worktree created it, is written to the single `.git/objects` directory. There's only one repository database. A worktree doesn't get its own object store — it would be wasteful and defeat much of the purpose (worktrees share objects specifically to avoid duplicating the repo's data).

What's separate is the **graph structure**, not the storage location:

```
.git/objects/  (one shared store)
  commit A  ← main's root
  commit B  ← main
  commit C  ← main
  commit X  ← kanban's root (orphan, no parent)
  commit Y  ← kanban
  commit Z  ← kanban
```

`main` is the ref chain `A→B→C`. `kanban` is the ref chain `X→Y→Z`. Both sets of commit objects sit in the same directory on disk, but `C` and `X` have no parent/child relationship — there's no edge connecting the two chains. That's what makes the orphan branch's history genuinely independent: not where it's stored, but the fact that walking its ancestry never reaches `main`'s commits.

If you ran `git log --all --graph`, you'd see two separate lines with no merge points connecting them, despite both being drawn from the same `.git/objects`.

### What This Means in Practice

- `git log` (no `--all`) in either worktree only walks that worktree's branch — it never sees the other branch's commits, because it traverses from `HEAD` and `kanban`'s commits simply aren't reachable from `main`'s `HEAD` or vice versa.
- `git gc` won't prune either branch's commits as long as both refs (`main` and `kanban`) exist pointing into the object store — reachability is computed across all refs, not per-worktree.
- A `git clone` of the repo brings down both histories (all objects, all refs) even though by default only one branch gets checked out into a working tree.
- Disk space is shared, not duplicated — if both branches happened to contain an identical file at some point, git stores that blob once and both commits' trees just point to it.

So: independent histories, shared storage. The worktree mechanism is what lets both of those checked-out states exist as real files on disk simultaneously, without either branch needing to know about the other.

---


**User**: [2026-06-30 21:01:44]

A git worktree seems to copy all the files in the repository to the worktree directory. I don't want this

---


**Claude**: [2026-06-30 21:01:52]

 This is a common misconception worth clearing up. A worktree does **not** copy all the files from the repository — it checks out only the files from the branch you specify.

When you run:

```bash
git worktree add .kanban-store kanban
```

Git checks out the `kanban` branch into `.kanban-store/`. Only the files that exist on the `kanban` branch appear there. If the `kanban` branch contains only:

```
.kanban-store/
  boards/
    my-project/
      todo/
        fix-login-bug.md
```

Then that's all that's in `.kanban-store/`. Your source code, `README.md`, `src/` — none of it appears there, because none of it is on the `kanban` branch.

The orphan branch is key here. Because `kanban` was created with `--orphan` and populated only with kanban files, the worktree directory will contain only those files. Git checks out the branch, not the repository. The two branches happen to share an object store, but their file trees are entirely different and neither bleeds into the other's working directory.

Where the "copies everything" concern is valid is with a **non-orphan branch** — if you added a worktree for `main` or a feature branch, it would check out all the files on that branch. The orphan branch sidesteps this entirely because it was never populated with anything except kanban files in the first place.

---


**User**: [2026-06-30 21:02:48]

how do i specify that i want an orphan branch for the worktree?

---


**Claude**: [2026-06-30 21:03:04]

 This is a gap in git's interface worth knowing about. There's no single command that creates an orphan branch and adds a worktree in one step. The `git worktree add` command has no `--orphan` flag — you have to do it in two steps.

The sequence is:

```bash
# 1. create the orphan branch (must be done from the main working tree)
git checkout --orphan kanban
git rm -rf .                    # clear inherited working tree files
git commit --allow-empty -m "kanban: initialize"
git checkout main               # return to main branch

# 2. now add the worktree pointing at the orphan branch
git worktree add .kanban-store kanban
```

The reason for the empty initial commit is that an orphan branch doesn't officially exist as a ref until it has at least one commit. `git worktree add` needs a real ref to check out — it can't point at an unborn branch.

---

### Cleaner Approach Using Plumbing Commands

The `git checkout --orphan` approach above briefly puts your main working tree into a strange state (all files staged for deletion). A cleaner alternative uses git's lower-level plumbing to create the orphan branch without ever touching the main working tree:

```bash
# create an empty tree object
EMPTY_TREE=$(git hash-object -wt tree /dev/null)

# create a commit with no parents pointing at the empty tree
INIT_COMMIT=$(echo "kanban: initialize" | git commit-tree $EMPTY_TREE)

# create the branch ref pointing at that commit
git update-ref refs/heads/kanban $INIT_COMMIT

# now add the worktree
git worktree add .kanban-store kanban
```

This never disturbs the main working tree — no branch switching, no staged deletions, no temporary weirdness. It's the approach `kanban init` should use internally.

---

### In Python with pygit2

```python
import pygit2

def create_kanban_worktree(repo_path: str, worktree_path: str) -> None:
    """Create an orphan kanban branch and add it as a worktree."""
    repo = pygit2.Repository(repo_path)

    # create an empty tree
    builder = repo.TreeBuilder()
    empty_tree = builder.write()

    # create a root commit with no parents
    sig = repo.default_signature
    commit_oid = repo.create_commit(
        None,          # don't update any ref yet
        sig, sig,
        "kanban: initialize",
        empty_tree,
        []             # no parents — this is the orphan root
    )

    # create the branch ref pointing at that commit
    repo.create_branch("kanban", repo.get(commit_oid), False)

    # add the worktree
    repo.add_worktree(worktree_path, "kanban")
```

After this, `.kanban-store/` exists as an empty directory (just the `.git` file) checked out to the `kanban` branch, and `kanban init` can proceed to create the board structure inside it normally using filesystem operations.

---


**User**: [2026-06-30 21:11:56]

As I make changes to the kanban worktree do I git add them from the main repository directory or from the .kanban-store folder. Right now when I do a git status I see that the .kanban-store is untracked and needs a git add command to track it

---


**Claude**: [2026-06-30 21:12:09]

 You work from inside `.kanban-store/` — or use `git -C .kanban-store` from anywhere. The worktree has its own index (staging area) and its own HEAD, so git operations targeting the `kanban` branch must be directed at that worktree.

What you're seeing with `git status` from the main working tree is expected and correct. Git sees `.kanban-store/` as an untracked directory in the main working tree — because it *is* untracked there. It's not a file or directory that belongs to the `main` branch. You don't want to `git add` it from the main repo.

The fix is to gitignore it from the main repo so it stops showing up:

```
# .gitignore (in the main repo root)
.kanban-store/
.kanban/
```

This tells git "these directories exist on disk but are not part of the main branch's tree" — which is exactly true. They'll disappear from `git status` output entirely.

---

### Staging and Committing Kanban Changes

All git operations for kanban files are run against the worktree:

```bash
# from inside the worktree
cd .kanban-store
git add boards/my-project/todo/fix-login-bug.md
git commit -m "kanban: task created"

# or equivalently, from anywhere using -C
git -C .kanban-store add boards/my-project/todo/fix-login-bug.md
git -C .kanban-store commit -m "kanban: task created"
git -C .kanban-store status
git -C .kanban-store push
```

The `-C` flag is what the `GitService` will use internally — it never needs to change the process working directory, it just prefixes every git command with `-C .kanban-store`.

---

### The Two Repos Mental Model

Once `.kanban-store/` and `.kanban/` are gitignored in the main repo, it helps to think of them as two entirely separate repositories that happen to share a `.git` objects directory:

```
Main repo                          Kanban worktree
─────────────────────────────      ─────────────────────────────
working dir: my-repo/              working dir: .kanban-store/
branch:      main                  branch:      kanban
git status:  shows src/, etc.      git status:  shows boards/, etc.
git add:     stages main files     git add:     stages kanban files
git push:    pushes main           git push:    pushes kanban
```

They're independent from a workflow perspective. The shared object store is an implementation detail you never need to think about during normal use.

---

