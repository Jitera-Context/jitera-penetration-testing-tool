# Vision

> Drafted from the goals and decisions the team has stated so far. The open
> questions at the end are for the team to answer; update this file as the
> vision firms up.

## What we are building

`jitera-pentest` is Jitera's own build of
[Strix](https://github.com/usestrix/strix), the open-source autonomous AI
penetration-testing tool. We fork it, maintain it internally, and run it under
the Jitera brand, while staying close enough to upstream to take every
improvement the Strix community ships.

## Goals

1. **Keep up with upstream easily.** However much we change, taking a new
   upstream release stays routine: minutes of work, with conflicts limited to
   the lines we changed.
2. **Run as Jitera.** Our brand appears wherever people look: CLI, terminal UI,
   reports and viewer. Our network identity appears wherever systems look: every
   request, including scan traffic, carries a Jitera User-Agent, so customers can
   recognize and allowlist our authorized testing.
3. **Keep the source clean and easy to maintain.** Engineers edit the real code
   and review real diffs on GitHub. No hidden build-time rewriting.
4. **Let quality lead development.** The eval decides whether a change is done:
   every feature must pass it. Results are recorded, so we know whether the tool
   is getting better or worse over time.
5. **Scale without slowing down.** Adding features, engineers or eval targets
   must not make syncing harder.

## Principles

- **Upstream is our base, not our competitor.** We change as little upstream
  code as we can, add our own code beside it, and contribute generic fixes back
  so our changes shrink over time.
- **Every change is recorded.** A checkpoint (the upstream commit we're based on)
  plus a patch per changed file means any upstream release can be replayed
  onto our work.
- **Identify ourselves honestly.** Our traffic says who it is. We don't send
  usage data to the upstream vendor, and we don't route users to its paid cloud.
- **Measured, not assumed.** A feature is finished when the eval says so, not
  when the code compiles.

## Not goals

- Renaming upstream internals (the `strix` package, `STRIX_*` settings). That
  would turn every sync into a manual merge.
- Using Strix Cloud or upstream's hosted services.
- Exact, repeatable finding counts. An AI agent varies run to run, so the eval
  measures vulnerability *categories* covered against a gate.

## How we'll know it's working

| Goal | Signal |
|---|---|
| Easy sync | `fork/dev sync` of an upstream release finishes in minutes; only our edited lines ever conflict |
| Runs as Jitera | `fork/dev audit` shows no upstream brand or endpoints outside features we disable |
| Clean source | `fork/dev verify` passes on `main`; the number of edited upstream files grows slowly |
| Quality leads | `main` passes the eval gate; coverage in `fork/dev eval-history` trends up |
| Scales | New features land in `strix/jitera/` and need few or no upstream edits |

## Open questions for the team

- Who are the users: Jitera's internal security team, customers, or both?
- How is it distributed: source checkout, binaries on our releases, a container?
- Which targets besides OWASP Juice Shop define "good"? (APIs, other apps?)
- What coverage do we commit to on the eval, once the gate is calibrated?
- Which product features beyond upstream's are on the roadmap? See
  [plans](../plans/README.md).
