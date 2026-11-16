# Vision

## Our vision

Build a penetration testing tool that helps users **detect attacks before they
happen and act on them**, and that, by **simulating real attackers**, lets
security and infrastructure teams test how well they detect and respond to
those risks.

## What it does

`jitera-pentest` is Jitera's own build of
[Strix](https://github.com/usestrix/strix), the open-source autonomous AI
penetration-testing tool, run under the Jitera brand. It serves two purposes.

### 1. Find the attack before an attacker does

The tool's AI agents behave like a real attacker against your own applications
and infrastructure: they map the attack surface, probe for weaknesses and prove
each one with a working proof of concept. You see what an attacker could do
before anyone does it, and you act on it:

- validated findings, not guesses, each with severity and fix guidance;
- reports for people (Markdown, PDF) and for pipelines (JSON, SARIF);
- runs on demand or in CI, so new weaknesses are caught as code changes.

### 2. Rehearse the defense

The same simulated attacks are an exercise for the people who defend. Run them
against your own systems and ask:

- Did our monitoring and alerts notice?
- How long did it take, and who was told?
- Did the security and infrastructure teams respond the way the playbook says?

By default the tool identifies itself: every request carries a Jitera
User-Agent, so a team can tell an exercise from a real attack and trace it. The
catch is that a scan which announces itself only tests whether you catch scans.
The next section is about running a realistic exercise without losing that
accountability.

## Our advantage: realistic, human-like simulation

You can only test detection against an attacker worth detecting. A scanner with
predictable requests and an obvious signature tells you one thing: whether you
catch obvious scanners. It says nothing about whether your team would notice
someone skilled.

So the tool doesn't behave like a scanner. It drives real browsers with a team
of agents that act like people: they navigate, sign in, fill forms, and chain
actions together across many sessions at once, the way a real user does, and the
way a real attacker does. That is what makes a defense rehearsal worth running.
You are testing against something that looks like the threats you actually face.

This gets more important every year. Attackers already use AI to blend into
ordinary traffic and slip past simple rules. You don't want to find out during a
real breach whether your team would have caught it. Running a realistic,
AI-driven adversary yourself, on your own systems and your own schedule, is how
you practice for that before it counts.

### Realistic, and still accountable

Realism and authorization don't have to fight. They live on separate channels:

- **Scope and permission come first.** Only authorized targets, within an
  agreed scope and time window. Realism never widens the scope.
- **Attribution stays available.** The traffic can look unremarkable, so it
  actually tests detection, while the exercise stays traceable another way: a
  known source address, a deconfliction contact, markers an investigator can
  confirm. A simulated attack is always traceable back to an authorized test. It
  just doesn't have to wave a flag at the detection you're trying to measure.

This changes how we think about the branded User-Agent. For finding and fixing
vulnerabilities, identifying ourselves is the right call: a team can allowlist
us and see exactly what we did. A detection exercise is the one case where that
marker gets in the way, so it would run without it and rely on out-of-band
attribution instead. That mode is a **planned capability**, not something the
tool does yet — see the [plans](../plans/README.md). Today every scan still
sends a Jitera User-Agent.

## Who it's for

- **Teams that own applications and infrastructure**, who want to find and fix
  weaknesses first.
- **Security and infrastructure teams**, who want to test their own detection
  and response against realistic attacks.

## How we build it

1. **Keep up with upstream easily.** Taking a new Strix release stays routine,
   however much we change; conflicts are limited to the lines we changed.
2. **Run as Jitera.** Our brand wherever people look; our User-Agent on every
   request, including scan traffic.
3. **Keep the source clean.** Engineers and agents edit the real code and
   review real diffs on GitHub.
4. **Let the eval lead.** A change is done when the eval says so: every feature
   must pass it.
5. **Agents lead development.** AI agents own the project's day-to-day work and
   prove every change through verify and the eval. People set direction and
   approve. See [agent-led development](../architecture/agent-led-development.md).
6. **Scale without slowing down.** More features, agents, people or eval
   targets must not make syncing harder.

## Principles

- **Authorized testing only.** Attack only systems you own or have written
  permission to test, within the agreed scope. Simulation must never become
  a real attack.
- **Accountable, always.** Every exercise is traceable to an authorized test:
  by default in the traffic itself, and out of band when a detection exercise
  needs the traffic to stay realistic. We send no usage data to the upstream
  vendor and don't route users to its paid cloud.
- **Proof over claims.** Findings come with a proof of concept; changes to the
  tool come with verify and eval results.
- **Upstream is our base.** We change as little upstream code as we can and
  contribute generic fixes back, so our changes shrink over time.

## Not goals

- Running against systems without permission, or causing real damage.
- Renaming upstream internals (the `strix` package, `STRIX_*` settings), which
  would turn every sync into a manual merge.
- Using Strix Cloud or upstream's hosted services.
- Exact, repeatable finding counts. An AI agent varies run to run, so the eval
  measures vulnerability *categories* against a gate.

## How we'll know it's working

| Goal | Signal |
|---|---|
| Find attacks first | The eval passes its gate, and coverage in `fork/dev eval-history` trends up |
| Rehearse the defense | Not measured yet. Measuring whether defenders detected a simulated attack is in the [plans](../plans/README.md) |
| Easy sync | An upstream release syncs in minutes; only our edited lines ever conflict |
| Runs as Jitera | `fork/dev audit` shows no upstream brand or endpoints outside disabled features |
| Agents lead, with proof | Agent PRs carry passing `fork/dev verify`, tests and, for behavior changes, an eval summary |
| Scales | New features land in `strix/jitera/` and need few or no upstream edits |

## Open questions

- How is the tool distributed: source checkout, binaries, a container?
- How should a defense rehearsal be run and scored: which signals from
  monitoring and response count as "detected"?
- When should the tool stay identified, and when (and how) should a detection
  exercise run realistically with out-of-band attribution instead?
- Which targets besides OWASP Juice Shop define "good"?
- What coverage do we commit to, once the eval gate is calibrated?
