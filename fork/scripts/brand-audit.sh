#!/usr/bin/env bash
# Brand-leak audit for the Jitera fork of Strix.
#
# Reports places where the upstream brand still reaches users or the network.
# Two categories:
#   outbound  upstream endpoints, keys and attribution that leave the machine
#             (strix.ai, usestrix releases, PostHog/Scarf, ghcr.io/usestrix, X-Title)
#   visible   quoted string literals that show "Strix" to a person
#             (CLI, TUI, viewer, reports)
#
# Internal identifiers are out of scope on purpose: the `strix` Python package,
# STRIX_* env vars, ~/.strix, the Go module path and class names stay upstream
# so syncs stay conflict-free.
#
# Usage: fork/scripts/brand-audit.sh [--strict] [--list]
#   --strict  exit 1 when any non-allowlisted outbound hit remains
#   --list    print every hit, not only the per-file summary
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
ALLOW_FILE="fork/brand-audit.allow"

strict=0
list=0
for arg in "$@"; do
  case "$arg" in
    --strict) strict=1 ;;
    --list) list=1 ;;
    *) echo "unknown option: $arg" >&2; exit 2 ;;
  esac
done

# Product surfaces only. Tests, upstream docs, agent knowledge packs and the
# compiled viewer bundle are excluded (the bundle is rebuilt from frontend/src).
SURFACES=(strix scripts containers pyproject.toml strix.spec)
EXCLUDES=(
  --exclude-dir=__pycache__ --exclude-dir=node_modules --exclude-dir=static
  --exclude-dir=skills --exclude='*_test.go' --exclude='*.md'
)

OUTBOUND_RE='strix\.ai|usestrix|scarf\.sh|phc_[A-Za-z0-9]{8,}|"X-Title": *"|X-Strix-'
VISIBLE_RE="[\"'\`][^\"'\`]*Strix[^\"'\`]*[\"'\`]"
# Skip tests, comments and docstrings: nothing there runs or is shown.
COMMENT_RE='_test\.go:|:[0-9]+:[[:space:]]*(#|//|/?\*|"""|r"""|`strix)'
# The Go module path is an internal identifier, not a brand surface.
OUTBOUND_IGNORE_RE="github\\.com/usestrix/strix/tui|${COMMENT_RE}"
VISIBLE_IGNORE_RE="$COMMENT_RE"

apply_allowlist() {
  if [[ -s "$ALLOW_FILE" ]]; then
    grep -vE -f <(grep -vE '^[[:space:]]*(#|$)' "$ALLOW_FILE") || true
  else
    cat
  fi
}

outbound="$(grep -rnIE "${EXCLUDES[@]}" "$OUTBOUND_RE" "${SURFACES[@]}" 2>/dev/null \
  | grep -vE "$OUTBOUND_IGNORE_RE" | apply_allowlist || true)"
visible="$(grep -rnIE "${EXCLUDES[@]}" --include='*.py' --include='*.go' --include='*.ts' \
  --include='*.tsx' --include='*.sh' "$VISIBLE_RE" strix scripts 2>/dev/null \
  | grep -vE "$VISIBLE_IGNORE_RE" | apply_allowlist || true)"

count() { if [[ -z "$1" ]]; then echo 0; else printf '%s\n' "$1" | wc -l | tr -d ' '; fi; }

report() {
  local title="$1" hits="$2"
  echo "== $title: $(count "$hits") hit(s) in $( [[ -z "$hits" ]] && echo 0 || printf '%s\n' "$hits" | cut -d: -f1 | sort -u | wc -l | tr -d ' ') file(s)"
  [[ -z "$hits" ]] && return
  if (( list )); then
    printf '%s\n' "$hits" | cut -c1-200
  else
    printf '%s\n' "$hits" | cut -d: -f1 | sort | uniq -c | sort -rn
  fi
  echo
}

report "outbound identity (network)" "$outbound"
report "visible brand (strings shown to people)" "$visible"

if (( strict )) && [[ -n "$outbound" ]]; then
  echo "brand-audit: outbound identity still points at upstream (see above)." >&2
  exit 1
fi
