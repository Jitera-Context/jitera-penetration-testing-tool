# Plans

Where the project stands and what comes next. Update this file in the same PR
that finishes or adds an item.

## Done

| PR | What |
|---|---|
| #3 | Fork architecture: checkpoint, patches, `fork/dev`, sync, skills |
| #4 | Rebrand to Jitera; Jitera User-Agent on our own calls and on scan traffic |
| #5 | Jitera README; `fork/OWNED` so replaced upstream files never conflict |
| #6 | Command renamed to `jitera-pentest` (`jitera` is the Jitera Gateway CLI) |
| #7 | Eval on OWASP Juice Shop with a category gate; GEPA optimization |
| #8 | `fork/dev eval`, `eval-history`, `gepa`; `/eval-run` and `/eval-gepa` |
| #9 | `.env.example`, and loading `.env` safely |
| #10 | The eval reads `.env` and checks the model before scanning; README eval guide |
| #11 | Docs: visions, architecture, plans; the rule that every feature must pass the eval |
| #12 | Vision: find attacks before they happen and rehearse the defense; agent-led development |
| #13 | Cartoon-style README images, drawn by `fork/scripts/render-architecture-images.py` |
| #14 | A security-focused README banner |
| #1, #2 | Dependency updates (pillow 13.0.0, pypdf 6.21.4), each tested on `main` before merge |

## Next, in priority order

| # | Item | Why | Done when | Eval |
|---|---|---|---|---|
| 1 | **Calibrate the eval gate** | `min_categories: 6` is a guess, not a measurement | Three real `fork/dev eval` runs recorded; gate set a little below typical coverage in a PR | This *is* the eval |
| 2 | **First real upstream sync** | We're behind upstream; its newer commits fix 12 of our failing upstream tests | Sync PR merged with a merge commit; tests and eval pass | Required |
| 3 | **Turn on CI** | No checks run on PRs: upstream's workflows aren't active in this repo | Lint, types, tests and `fork/dev verify` run on every PR and block merges | — |
| 4 | **Eval in CI** | "Every feature passes the eval" should be enforced, not just checked by reviewers | A quick eval runs on PRs that touch agent behavior; a full one runs nightly on `main` | — |
| 5 | **Update uv** | The local uv 0.8.8 can't parse `exclude-newer = "5 days"` and rewrites `uv.lock` unless run with `--frozen`. Dependabot #1 and #2 were merged after testing with uv 0.13.8 through `uvx` | A current uv locally and in CI; every dependency bump tested on `main` before merge | Required |
| 6 | **Release pipeline** | The binary is still named `strix`, and we publish no releases | `jitera-pentest` binaries on our releases; installer and self-update use them | Required |
| 7 | **GEPA optimization run** | Better agent instructions, measured | A GEPA result validated by repeated evals and adopted in a PR | Required |
| 8 | **Make `fork/dev test` finish** | `tests/test_tool_call_ids_providers.py` hangs on a live HTTPS call, on untouched upstream too, so the full run never ends. PRs #13 and #14 ran the suite without that file | `fork/dev test` completes without network access (a per-test timeout, or the file skipped with a reason); the hang reported upstream | — |
| 9 | **Stop the viewer's PDF export from reaching the upstream vendor** | "Export report to PDF" builds an encrypted PDF locally, then emails it through `app.strix.ai` (`STRIX_APP_URL`). That breaks "no data to the upstream vendor" | The export is disabled, or replaced by a local download; the README lists PDF again only if it works locally | — |
| 10 | **Keep upstream tests out of the real home and working folder** | Every suite run leaves two fake runs (no target, status `running`) in `./strix_runs` and rewrites `~/.strix/cli-config.json` and `cli-identity.json` plus a wallet cache, in the developer's real home (seen on `main`; not yet checked at the checkpoint). Our own tests use a throwaway home | A full test run leaves the working folder and home unchanged; if upstream does it too, reported upstream | — |

## Later

- **Rehearse the defense (vision, part 2).** Run a simulated attack against a
  team's own systems and record whether, and how fast, their monitoring
  detected it. First step: decide which signals count as "detected".
- **Realistic adversary mode, with out-of-band attribution.** For detection
  exercises, let the tool's browser-driven, multi-agent simulation run without
  the loud Jitera User-Agent, while staying attributable to an authorized test
  another way (known source, deconfliction contact, confirmable markers). Today
  scan traffic always carries the User-Agent. This is the "our advantage"
  capability from the vision; design it so realism can never widen the
  authorized scope.
- **The same agent rules for every coding agent.** `CLAUDE.md` covers Claude
  Code; other agents read `AGENTS.md`, which is upstream's file. Decide whether
  to add our rules there or list it in `fork/OWNED`.

- **More eval targets.** API-focused checks, and other deliberately vulnerable
  training apps, each with its own `eval/baseline/<name>.yaml`.
- **Brand assets.** A real logo for the viewer and PDF reports (today a "J" mark).
- **Sandbox image.** Keep upstream's image pinned by digest, or publish ours.
- **Contribute upstream.** Send generic fixes to `usestrix/strix`, including
  fixes for the 9 upstream tests that also fail on upstream's `main`.

## Open decisions

- Who the users are, and how the tool is distributed (see the
  [vision](../visions/README.md)).
- The coverage level we commit to once the gate is calibrated.
- The CI budget for eval runs: per PR, nightly, per release.
