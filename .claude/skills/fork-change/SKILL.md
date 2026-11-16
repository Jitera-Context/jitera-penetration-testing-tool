---
name: fork-change
description: Write or change code in the Jitera fork of Strix (branding, User-Agent, agent tools, skills, CLI commands, bug fixes). Engineers edit the source directly; fork/dev save records every change since the checkpoint as patches for syncing. Use for any change to this repo's code.
---

# Change code in the Jitera fork

- Edit the source directly. Git and GitHub show the changed code.
- `fork/CHECKPOINT` holds the upstream commit hash our changes are based on.
- `fork/patches/<path>.patch` records every change since that checkpoint: edited,
  new and deleted files. Patches are only used by `fork/dev sync`.
- `fork/` and `.claude/` are the tooling itself: never patched.

## Where code goes

| Change | Put it in |
|---|---|
| Agent tool | `strix/jitera/tools/<name>.py` (`@function_tool`, like `strix/tools/thinking/tool.py`), returned from `get_tools()` |
| Pentest knowledge | `strix/jitera/skills/<category>/<name>.md`. Upstream's path replaces upstream's skill |
| CLI subcommand | `strix/jitera/commands/<name>.py` with `run(argv) -> int`, registered in `COMMANDS` |
| Default for a `STRIX_*` setting | `ENV_DEFAULTS` in `strix/jitera/bootstrap.py` |
| Brand value (name, URL, User-Agent) | `strix/jitera/brand.py` |
| Behaviour upstream has no hook for | edit the upstream file in place, as small as possible |
| Our tests | `tests/jitera/` |

Prefer `strix/jitera/` plus upstream's hooks. Small edits to upstream files mean fewer sync conflicts.

## Loop

1. Edit files. Run with `uv run --frozen jitera ...`.
2. `git add` any new file. `fork/dev save` only records tracked files, and `fork/dev status` lists untracked ones.
3. `fork/dev test`
4. `fork/dev save`: writes, updates or removes patches and stages them.
   For an edited upstream file, replace the `Title:` / `Why:` TODO lines in its patch.
   New files get a header automatically.
5. Commit the code and its patches together. CI runs `fork/dev verify`, which fails if they differ.

If a patch file conflicts while merging branches, resolve the code, then run `fork/dev save`. Never edit a patch by hand.

## Rules

- To use brand values in an upstream file, put `from strix.jitera import brand  # noqa: E402  (Jitera fork)` on its own line right above the first use. Then read `brand.current().name` etc.
- Upstream tests run with the `UPSTREAM` profile; only the `jitera` command activates `JITERA`. Keep upstream tests green without editing them.
- Never rename the `strix` package, `STRIX_*` env vars, `~/.strix`, the Go module path or class names.
- Traffic sent to scan targets keeps a neutral User-Agent.
- Always run uv with `--frozen`. An old uv rewrites `uv.lock`; never commit an unexpected `uv.lock` change.
- Generated files (`strix/interface/viewer/static/`, `uv.lock`) are never patched. Rebuild them (`make viewer`, `uv lock`).
