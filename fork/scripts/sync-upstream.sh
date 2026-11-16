#!/usr/bin/env bash
# Take a new upstream Strix into the Jitera fork.
#
#   fork/dev sync [vX.Y.Z]     start (default: upstream main)
#   fork/dev sync --continue   finish after fixing failed patches
#   fork/dev sync --abort      drop an unfinished sync
#
# 1. back to the checkpoint (fork/CHECKPOINT): remove all patched changes
# 2. take the latest upstream (a clean merge, because step 1 left pure upstream)
# 3. re-apply fork/patches with a 3-way merge; you fix any that fail
# 4. move the checkpoint, refresh the patches, and squash it all into ONE merge
#    commit (parents: main, new upstream) on a sync/ branch for PR review
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

UPSTREAM_URL="https://github.com/usestrix/strix.git"
SYNC_BASE="${SYNC_BASE:-origin/main}"
STATE="$(git rev-parse --git-dir)/fork-sync-state"
GENERATED=(strix/interface/viewer/static uv.lock)

die() { echo "sync-upstream: $*" >&2; exit 1; }

finish() {
  [[ -f "$STATE" ]] || die "no sync in progress."
  # shellcheck disable=SC1090
  source "$STATE"
  [[ "$(git branch --show-current)" == "$BRANCH" ]] || die "switch back to $BRANCH first."
  local f
  while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    if [[ -f "$f" ]] && grep -qE '^(<<<<<<<|>>>>>>>)( |$)' "$f"; then
      die "resolve the conflict markers in $f, then run fork/dev sync --continue."
    fi
  done < <(git ls-files -u | awk '{print $4}' | sort -u)
  git rerere >/dev/null 2>&1 || true        # remember these fixes for the next sync

  echo "Refreshing patches against upstream $REF"
  fork/dev save | grep -v '^Next:' || true
  if fork/dev patches | grep -q ' strix/interface/viewer/frontend/'; then
    echo "Rebuilding the viewer bundle (frontend is patched)"
    make viewer
  fi
  if ! uv lock --check >/dev/null 2>&1; then
    echo "Note: uv.lock may need 'uv lock' (use a current uv; an old uv rewrites the whole lock)."
  fi

  git add -u
  git add -A -- fork/patches fork/CHECKPOINT strix/interface/viewer/static
  local tree commit short
  tree="$(git write-tree)"
  short="$(git rev-parse --short "$NEW_SHA")"
  commit="$(git commit-tree "$tree" -p "$BASE_SHA" -p "$NEW_SHA" \
    -m "chore(sync): merge upstream $REF ($short)")"
  git reset -q --hard "$commit"
  rm -f "$STATE"
  fork/dev verify
  cat <<EOF

Synced to upstream $REF ($short). Checkpoint is now $short.
One merge commit on $BRANCH. Next:
  fork/dev test
  git push -u origin $BRANCH
  open a PR into main and merge it with "Create a merge commit" (never squash or rebase:
  the checkpoint commit must stay in history).
EOF
}

abort() {
  [[ -f "$STATE" ]] || die "no sync in progress."
  # shellcheck disable=SC1090
  source "$STATE"
  git reset -q --hard "$BASE_SHA"
  rm -f "$STATE"
  echo "Sync aborted. $BRANCH is back at $(git rev-parse --short "$BASE_SHA"); delete it with: git switch main && git branch -D $BRANCH"
}

start() {
  local ref="$1" target target_sha old behind short branch base_sha f
  [[ ! -f "$STATE" ]] || die "a sync is already in progress. Fix it and run fork/dev sync --continue, or fork/dev sync --abort."
  [[ -z "$(git status --porcelain --untracked-files=no)" ]] || die "commit or stash your changes first."

  # One-time remote setup: fetch main + tags only, and never allow a push.
  if ! git remote get-url upstream >/dev/null 2>&1; then
    git remote add upstream "$UPSTREAM_URL"
    git config remote.upstream.fetch '+refs/heads/main:refs/remotes/upstream/main'
    git config --add remote.upstream.fetch '+refs/tags/*:refs/tags/upstream/*'
    git remote set-url --push upstream DISABLE_PUSH_TO_UPSTREAM
  fi
  git config rerere.enabled true
  git config rerere.autoupdate true

  [[ "$SYNC_BASE" == origin/* ]] && git fetch --quiet origin "${SYNC_BASE#origin/}"
  git fetch --quiet upstream
  if [[ "$ref" == "main" ]]; then target="upstream/main"; else target="refs/tags/upstream/${ref}"; fi
  target_sha="$(git rev-parse --verify --quiet "$target^{commit}")" || die "unknown upstream ref: $ref"

  behind="$(git rev-list --count "$SYNC_BASE..$target_sha")"
  [[ "$behind" != "0" ]] || { echo "Already up to date with $ref."; exit 0; }

  branch="sync/upstream-${ref//\//-}-$(date +%Y%m%d)"
  git switch --quiet -C "$branch" "$SYNC_BASE"
  base_sha="$(git rev-parse HEAD)"
  old="$(awk 'NR==1 {print $1}' fork/CHECKPOINT)"
  fork/dev verify >/dev/null || die "patches on $SYNC_BASE don't match its code. Run fork/dev save there first."
  printf 'BASE_SHA=%s\nNEW_SHA=%s\nREF=%s\nBRANCH=%s\n' "$base_sha" "$target_sha" "$ref" "$branch" >"$STATE"
  short="$(git rev-parse --short "$target_sha")"

  echo "1/3 Back to checkpoint $(git rev-parse --short "$old"): removing all patched changes"
  fork/dev unapply >/dev/null
  for f in "${GENERATED[@]}"; do
    if ! git diff --quiet "$old" -- "$f"; then
      git rm -r -q --ignore-unmatch -- "$f"
      git checkout -q "$old" -- "$f"
    fi
  done
  if ! git diff --cached --quiet || ! git diff --quiet; then
    git commit -q -am "tmp(sync): back to checkpoint"
  fi

  echo "2/3 Taking $behind upstream commit(s) up to $ref ($short)"
  git merge --quiet --no-ff --no-edit -m "tmp(sync): merge upstream $ref" "$target_sha" \
    || die "merge conflict after returning to the checkpoint; a change was committed without its patch. Run fork/dev sync --abort, then fork/dev save on main."
  printf '%s %s\n' "$target_sha" "$ref" >fork/CHECKPOINT

  echo "3/3 Re-applying patches"
  if fork/dev apply; then
    finish
  else
    cat <<EOF

Sync paused on $branch. After fixing the files above:
  fork/dev sync --continue      refreshes the patches and makes the merge commit
EOF
    exit 1
  fi
}

case "${1:-main}" in
  --continue) finish ;;
  --abort) abort ;;
  -*) die "unknown option: $1" ;;
  *) start "${1:-main}" ;;
esac
