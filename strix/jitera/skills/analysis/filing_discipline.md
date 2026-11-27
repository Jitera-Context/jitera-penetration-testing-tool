---
name: filing-discipline
description: File every confirmed issue the moment you confirm it, so a cut-off run never loses validated findings. Filing is continuous and is never a reason to stop hunting early
---

# Filing discipline — confirmed means filed, and filing never ends the hunt

Scans here lose findings two ways: validators **confirm** an issue but never call
the report tool, and the run is cut off (budget/time) with a queue of confirmed
issues still unreported. Filing as you go fixes both — and because you file as
you go, you never have to stop probing early to make room for reporting.

## Rules

1. **File the moment you confirm.** As soon as you have evidence that proves an
   issue, call `create_vulnerability_report` (or `create_dependency_report` for a
   known-CVE dependency) **immediately** — before moving to the next probe. Do
   not collect confirmed issues to file "at the end": a run that is cut off loses
   every unfiled one.
2. **File every item a coverage tool returns.** `detect_vulnerable_components`
   (each `vulnerable` entry → one `create_dependency_report`), `scan_static_exposure`
   (each verified secret / live hidden endpoint), `check_payload_fired`
   (`fired: true` → file), `detect_serialized_objects` (each confirmed, controllable
   blob). One confirmed result = one filed report. Don't summarize them in a note.
3. **A sub-agent files its own findings — and keeps hunting.** Do not hand a
   confirmed issue back to the root as prose for the root to file; the root may
   never get to it. File it with `create_*`, then **keep working your assigned
   surface**. Filing a finding is not the end of your task: call `agent_finish`
   only when you have genuinely exhausted the techniques, variants, and inputs
   for your area — not as soon as you have something to report.
4. **Filing is continuous; it is never a reason to stop.** Because every
   confirmation is filed on the spot, there is no reporting backlog to protect
   and no reason to stop probing to "save budget for the report". Keep hunting
   until the runtime stops you or you have truly run out of new avenues. If you
   are cut off mid-probe, everything you confirmed is already on file.
5. **One issue, one report.** Distinct vulnerabilities are separate reports even
   on the same endpoint (e.g. an IDOR and an info leak on `/api/x` are two). Do
   not merge several issues into one finding — it undercounts the real result.

## Finishing a deep scan

A reconciled coverage board is **not** a signal to finish. "Every class has a
coverage entry" means each class was *looked at* — it does not mean everything
in it was *found*. One class usually hides several distinct issues.

In a **deep** scan, when the board looks complete and budget remains, go deeper
instead of finishing:

- Close every `needs_follow_up` surface and every gap the runtime flags as
  unexamined.
- Re-probe surfaces you closed as `no_issue_found` with new techniques, variant
  payloads, encodings, and other auth/role contexts.
- Chain confirmed findings into higher-impact, end-to-end attacks.
- Enumerate and exercise inputs, roles, and flows you have not tried yet.

The runtime enforces this: in deep mode `finish_scan` is refused while gaps or
unresolved surfaces remain, and for the first few attempts even on a clean
board. When it is refused, follow its `action_required` and dispatch another
wave — do not just call `finish_scan` again.
