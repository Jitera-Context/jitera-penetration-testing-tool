## What and why

<!-- What changes, and why. Link the plan item if there is one (docs/plans). -->

## Eval

Every feature must pass the eval (docs/architecture/eval-driven-development.md).

- [ ] **This PR changes agent behavior** (prompts, skills, tools, scan flow, runtime, LLM settings, scan traffic, or an upstream sync)
  - [ ] `fork/dev eval` passed on a fresh scan (exit 0); summary pasted below
  - [ ] No category that recent runs found is now missed (`fork/dev eval-history`)
- [ ] **Not a behavior change** (docs, `fork/` tooling, tests or CI only): no eval needed

```text
<!-- paste the fork/dev eval summary: coverage, gate, missed categories; plus scan mode and cost -->
```

## Fork workflow

- [ ] `fork/dev test` passes
- [ ] `fork/dev save` run; code and patches committed together (`fork/dev verify` passes)
- [ ] New patches to upstream files have a real `Title:` and `Why:`
- [ ] A sync PR will be merged with **Create a merge commit**
