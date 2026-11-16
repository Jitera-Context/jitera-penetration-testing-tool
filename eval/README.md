# Eval: OWASP Juice Shop

Runs `jitera-pentest` against [OWASP Juice Shop](https://owasp.org/www-project-juice-shop/), a deliberately vulnerable app OWASP publishes for security training and tool benchmarking, and checks that the scan still finds what it should.

Only scan targets you are authorized to test. The default target is OWASP's public demo, which exists for this purpose.

## How a run is judged

An LLM-driven scan never produces exactly the same findings twice, so the eval doesn't compare counts. It compares **vulnerability categories**:

1. `baseline/juice-shop.yaml` lists 12 categories Juice Shop is known to contain (SQL injection, XSS, broken access control, and so on), with the CWE ids and keywords that identify each.
2. Every finding is mapped onto those categories by CWE or keyword.
3. The run **passes** when it covers at least `min_categories` (default 6). That's the "X issues" gate: stable across normal variance, but it fails when the agent stops finding whole classes of vulnerability.

Each run is recorded in `results/` (`<timestamp>.json`, `latest.json`, and an append-only `history.jsonl`), so coverage can be tracked over time. Results stay on the machine that ran them; they're not committed.

## Run it

```bash
export JITERA_PENTEST_LLM="openrouter/z-ai/glm-5.3"
export LLM_API_KEY="your-api-key"

fork/dev eval --check                         # is the target up? (no scan, no cost)
fork/dev eval                                 # scan, score, gate
fork/dev eval --from-run DIR                  # score a finished run, no scan
fork/dev eval --scan-mode quick --max-budget 5
fork/dev eval --target http://localhost:3000
fork/dev eval-history                         # the last 10 recorded runs
```

`fork/dev eval` is a shortcut for `uv run --frozen python -m eval.run_eval`.

In Claude Code, `/eval-run` runs the eval for you: it checks the target, asks before
a paid scan, reads the exit code, and reports coverage and misses.

| Exit code | Meaning |
|---|---|
| 0 | Pass: coverage at or above the gate |
| 1 | Regression: coverage below the gate |
| 2 | Setup problem (bad baseline, the scan produced no output) |
| 3 | Target unreachable. Not a regression: the public demo is often down |

If the demo is down, run Juice Shop locally and pass `--target`:

```bash
docker run --rm -p 3000:3000 bkimminich/juice-shop:v20.4.0
```

To change what's expected, edit `baseline/juice-shop.yaml`: the target, `min_categories`, scan mode, budget, or the categories themselves.

## Optimize with GEPA

[GEPA](https://pypi.org/project/gepa/) (reflective Pareto prompt evolution) improves the instruction block the agent receives. It scores each candidate with this eval, reflects on the categories it missed, proposes a revised instruction, and keeps the best. It optimizes a general, reusable instruction, never target-specific answers.

`gepa` is not a product dependency. Add it only for an optimization run:

```bash
# Check the loop works: stub scoring and stub reflection, no scans, no LLM spend
fork/dev gepa --dry-run

# Real run: every metric call is a full scan (minutes to hours, real LLM cost)
fork/dev gepa --max-metric-calls 6
fork/dev gepa --max-metric-calls 6 --target http://localhost:3000
```

`fork/dev gepa` is a shortcut for `uv run --frozen --with gepa==0.1.4 python -m eval.gepa.optimize`.
Dry-run output goes to `results/`, so it never gets committed.

In Claude Code, `/eval-gepa` walks through it: dry run, cost estimate and your go-ahead,
the real run, then validating the result with the eval before adopting it.

- The best instruction is written to `gepa/optimized_instructions.txt`. Try it with `run_eval --instruction-file eval/gepa/optimized_instructions.txt` before adopting it.
- GEPA checks its budget between iterations, so it can make a few more calls than `--max-metric-calls` (the dry run made 8 against a cap of 6). Size the cap and the per-scan budget with that in mind.
- The reflection model is `STRIX_LLM` (set via `JITERA_PENTEST_LLM`), or `--reflection-model`.

## Files

| Path | What |
|---|---|
| `baseline/juice-shop.yaml` | Target, gate, scan settings, expected categories |
| `score.py` | Maps findings to categories. Pure and deterministic |
| `harness.py` | Runs one headless scan in a fresh directory |
| `run_eval.py` | The CLI: scan or score, gate, record |
| `gepa/adapter.py` | GEPA adapter: scores candidates, writes reflection feedback |
| `gepa/optimize.py` | The GEPA CLI, with `--dry-run` stubs |
| `results/` | Local run history (git-ignored) |

Tests: `tests/jitera/test_eval.py` (always runs) and `tests/jitera/test_eval_gepa.py` (runs only when gepa is installed).
