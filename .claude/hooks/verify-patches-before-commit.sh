#!/usr/bin/env bash
# Claude Code PreToolUse hook (Bash), set in .claude/settings.json.
#
# Before Claude runs `git commit` in this fork, check that the commit keeps the
# code and fork/patches in step: fork/dev verify --staged on what the commit
# records (the working tree for `git commit -a`). On a mismatch the call is
# blocked (exit 2) and Claude is told why and what to run. Any other command,
# or a commit in another repository, passes through untouched.
set -uo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<<"$input")"
cwd="$(jq -r '.cwd // empty' <<<"$input")"
[[ -n "$command" ]] || exit 0

commit_re='(^|[;&|({[:space:]])git([[:space:]]+-C[[:space:]]+[^[:space:]]+)?[[:space:]]+commit([[:space:]]|$)'
[[ "$command" =~ $commit_re ]] || exit 0

# The repository the commit runs in: `git -C <dir> commit`, else a leading
# `cd <dir> && ...`, else the session's folder.
dir="${cwd:-$PWD}"
gitc_re='git[[:space:]]+-C[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:]]+)[[:space:]]+commit'
cd_re='(^|[;&|][[:space:]]*)cd[[:space:]]+("[^"]+"|'"'"'[^'"'"']+'"'"'|[^[:space:];&|]+)'
if [[ "$command" =~ $gitc_re ]]; then
  dir="${BASH_REMATCH[1]}"
elif [[ "$command" =~ $cd_re ]]; then
  dir="${BASH_REMATCH[2]}"
fi
dir="${dir#[\"\']}"
dir="${dir%[\"\']}"
dir="${dir/#\~/$HOME}"
[[ "$dir" == /* ]] || dir="${cwd:-$PWD}/$dir"

root="$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null)" || exit 0
[[ -x "$root/fork/dev" && -f "$root/fork/CHECKPOINT" ]] || exit 0

# `git commit -a` / `--all` records every tracked change: verify the working tree.
all_re='commit([[:space:]]+[^;&|]*)?[[:space:]](-[[:alpha:]]*a[[:alpha:]]*|--all)([[:space:]]|$)'
mode=(--staged)
[[ "$command" =~ $all_re ]] && mode=()

if ! out="$("$root/fork/dev" verify "${mode[@]+"${mode[@]}"}" 2>&1)"; then
  cat >&2 <<EOF
Commit blocked: the code and fork/patches/ are out of step in what this commit records.

$out

Every change since fork/CHECKPOINT needs its patch, committed with the code
(.claude/skills/fork-change/SKILL.md):
  1. git add the code changes that belong to this commit
  2. fork/dev save            (writes and stages the patches)
  3. fill in Title/Why in any patch that still says TODO
  4. leave out patches for code you are not committing
     (git restore --staged fork/patches/<file>.patch)
Check with: fork/dev verify --staged
EOF
  exit 2
fi
exit 0
