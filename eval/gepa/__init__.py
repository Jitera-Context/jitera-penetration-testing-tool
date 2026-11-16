"""GEPA optimization of the agent's eval instructions.

GEPA (reflective Pareto prompt evolution) proposes variations of an instruction
block, scores each by running the eval, reflects on what categories were missed,
and keeps the Pareto-best. It optimizes a reusable instruction, never anything
target-specific.

The ``gepa`` package is not a runtime dependency of the product. Install it only
for an optimization run:

    uv run --frozen --with gepa==0.1.4 python -m eval.gepa.optimize --dry-run
"""
