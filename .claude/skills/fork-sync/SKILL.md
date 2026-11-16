---
name: fork-sync
description: Take a new upstream Strix (usestrix/strix) into the Jitera fork with fork/dev sync. It goes back to the checkpoint, removes our changes, takes the latest upstream and re-applies our patches; fix any that fail, then open the PR. Use when asked to sync, update from upstream, or take a new Strix release.
---

# Sync upstream into the Jitera fork

`fork/CHECKPOINT` holds the upstream commit our changes are based on, and
`fork/patches/` records every change since then. `fork/dev sync`:

1. branches `sync/upstream-<ref>-<date>` from `origin/main`
2. goes back to the checkpoint: removes all patched changes, leaving pure upstream
3. takes the latest upstream (a clean merge)
4. re-applies every patch with a 3-way merge; files listed in `fork/OWNED` keep our version instead
5. moves the checkpoint, refreshes the patches, and squashes everything into ONE merge commit (parents: main, new upstream)

## Steps

1. Start clean: `git status` shows no changes, and `fork/dev verify` passes on main.
2. `fork/dev sync` (upstream main) or `fork/dev sync v1.7.2` (a release tag).
3. If it stops on a failed patch:
   - **CONFLICT**: the file has a block from `<<<<<<< ours` (new upstream) to `>>>>>>> theirs` (our patch). Keep upstream's new code and re-apply our change. This also covers upstream adding a file we added too: merge both contents.
   - **FAILED**: the file moved or was deleted upstream. Re-make our change where the code lives now, and `git add` any new file.
   - Then run `fork/dev sync --continue`. It refuses while conflict markers remain.
   - `fork/dev sync --abort` drops the sync.
   - `= kept ours  <file> (upstream changed it ...)`: not an error. Run the printed `git diff` and copy anything useful from upstream into our version.
4. `fork/dev test`
5. `git push -u origin <branch>` and open a PR into `main` titled `Sync upstream <ref> (<sha>)`. List the patches that conflicted and how you fixed them.
6. Merge with **Create a merge commit**. Never squash or rebase: the checkpoint commit must stay in history, or `fork/dev verify` fails.

## Rules

- Fix our change, not upstream's tests.
- If it notes that `uv.lock` may need `uv lock`, run it only with a current uv.
- Report the outcome plainly: commits taken, patches applied, patches fixed, test and audit results.
