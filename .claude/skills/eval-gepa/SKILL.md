---
name: eval-gepa
description: Optimize the agent's instructions for the Juice Shop eval with GEPA (fork/dev gepa). Dry-run first, confirm the cost, run with a small budget, then validate the result with the eval before adopting it. Use when asked to run GEPA, tune or optimize the agent's prompt or instructions, or raise eval coverage.
---

# Optimize instructions with GEPA

GEPA proposes revisions of an instruction block given to the agent, scores
each with the Juice Shop eval, reflects on the categories it missed, and keeps
the best. `gepa` is not a product dependency; `fork/dev gepa` adds it per run.

## Steps

1. **Dry run, always first.** `fork/dev gepa --dry-run`
   No scans, no LLM. Expect `seed score ... best score ...`. If it fails, fix
   that before spending money.
2. **Work out the cost and confirm with the user.** Every metric call is a full
   scan at the baseline's `scan_mode` and up to `max_budget_usd`. GEPA checks
   its budget between iterations, so it can make a few more calls than
   `--max-metric-calls` (the dry run made 8 against a cap of 6). Give the user
   the worst case, roughly (cap + 2) × budget, and wait for a yes. A model
   LiteLLM can't price (a gateway or self-hosted model) records no cost, so the
   budget can't stop a scan (up to 4 hours each) unless the user sets
   `JITERA_PENTEST_LLM_INPUT_COST_PER_MTOK` and `..._OUTPUT_COST_PER_MTOK`.
3. **Check the target is up.** `fork/dev eval --check` (no scan, no cost).
   Exit `3` means it's down: use a local Juice Shop (see `/eval-run`) and pass
   the same `--target` to every eval you run.
4. **Real run.** With `JITERA_PENTEST_LLM` and `LLM_API_KEY` set (in `.env` or the shell),
   plus `LLM_API_BASE` for a gateway or self-hosted model (`openai/<model id>`):
   `fork/dev gepa --max-metric-calls 6`
   Options: `--target URL` (a local Juice Shop), `--reflection-model MODEL`,
   `--seed-file FILE` (start from an earlier result). The best instruction goes to `eval/gepa/optimized_instructions.txt`.
5. **Validate before adopting.** Run the eval with and without it, ideally more
   than once each, and compare coverage:
   `fork/dev eval --instruction-file eval/gepa/optimized_instructions.txt`
6. **Review the text.** It must stay general: no target-specific answers, no
   payloads, no identifying markers beyond our User-Agent. Reject it otherwise.
7. **Adopt deliberately.** Committing `optimized_instructions.txt` records it
   for future eval runs (`fork/dev save`, then commit). Making the agent use it
   by default is a code change: follow `/fork-change`.

## Rules

- Never run a real optimization without the user's go-ahead on cost.
- Dry-run output goes to `eval/results/` and is never committed.
- Report seed vs best score, metric calls used, scan spend, and the
  validation comparison. An improvement in GEPA's own score alone is not
  enough to adopt.
