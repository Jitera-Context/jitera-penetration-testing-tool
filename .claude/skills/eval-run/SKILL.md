---
name: eval-run
description: Run the OWASP Juice Shop eval for jitera-pentest (fork/dev eval), read the category-coverage gate, and track results over time. Use when asked to run the eval, check whether the scanner regressed, score a finished scan run, look at eval history, or calibrate the pass gate.
---

# Run the Juice Shop eval

The eval scans OWASP Juice Shop, maps findings to the 12 categories in
`eval/baseline/juice-shop.yaml`, and passes when at least `min_categories` are
covered. Details: `eval/README.md`.

## Before a real scan

- A real scan takes minutes to hours and spends LLM money. Unless the user
  already asked for a real scan, say so and confirm before starting one.
  Scoring an existing run (`--from-run`) is free.
- Needs `JITERA_PENTEST_LLM` and `LLM_API_KEY`, normally in the checkout's
  `.env` (`cp .env.example .env`), and Docker running for the sandbox. Never
  print or commit the key.
- Only scan Juice Shop: the baseline's target (OWASP's public demo) or a local
  instance. Never point the eval at anything else.

## Steps

1. `fork/dev eval-history` to see earlier runs and the usual coverage, and
   `fork/dev eval --check` to see whether the target is up (no scan, no cost).
2. Run one of:
   - `fork/dev eval` (the baseline's target and settings)
   - `fork/dev eval --scan-mode quick --max-budget 5` (cheaper check)
   - `fork/dev eval --from-run strix_runs/<run>` (score a finished run, no scan)
3. Act on the exit code:
   - `0` pass.
   - `1` regression. Before calling it a capability regression, open the run's
     `run.json`: if the scan stopped early (budget, rate limit, error), it's a
     run problem, not the agent. Compare the missed categories with
     `eval/results/latest.json` and earlier history.
   - `2` setup problem: read the error (bad baseline, no run directory).
   - `3` target unreachable. Not a regression. Start a local Juice Shop and rerun:
     `docker run --rm -p 3000:3000 bkimminich/juice-shop:v20.4.0`, then
     `fork/dev eval --target http://localhost:3000`.
4. Report: coverage (covered/total), the gate, the missed categories, scan cost,
   and pass or regression. Say whether it was a fresh scan or a re-score of an
   old run.

## Calibrating the gate

`min_categories: 6` is a starting value. After about three real runs, set it a
little below the typical coverage in `eval/baseline/juice-shop.yaml`. That file
is part of the source, so follow the fork workflow: `fork/dev save`, then commit.

## Rules

- Never lower the gate or edit the baseline just to turn a failing run green.
  If the baseline is wrong, say why in the commit.
- `eval/results/` is local history and git-ignored. Don't commit it.
