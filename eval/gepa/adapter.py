"""The GEPA adapter: how a candidate instruction is scored and reflected on.

A *candidate* is ``{"instructions": "<text>"}``. The text is given to the agent
as an extra instruction file; the eval score (fraction of baseline categories
covered) is the metric GEPA maximizes.
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gepa.core.adapter import EvaluationBatch, GEPAAdapter

from eval._lib import load_findings
from eval.harness import run_scan
from eval.score import score_findings


if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from eval._lib import Baseline


COMPONENT = "instructions"

# A rollout runs one candidate on one task and returns (score in [0,1], breakdown).
Rollout = Callable[[str, dict[str, Any]], "tuple[float, dict[str, Any]]"]


def make_tasks(baseline: Baseline) -> list[dict[str, Any]]:
    """The eval instances GEPA trains on. One per target for now."""
    return [
        {
            "target": baseline.target,
            "scan_mode": baseline.scan_mode,
            "max_budget_usd": baseline.max_budget_usd,
            "baseline": baseline.name,
        }
    ]


def scan_rollout(baseline: Baseline) -> Rollout:
    """Real rollout: run a scan with the candidate instructions, then score it.

    Each call is a full pentest — minutes to hours and real LLM spend — so keep
    ``max_metric_calls`` small.
    """
    categories = list(baseline.categories)

    def rollout(instructions: str, task: dict[str, Any]) -> tuple[float, dict[str, Any]]:
        with tempfile.TemporaryDirectory(prefix="jitera-gepa-") as tmp:
            tmp_path = Path(tmp)
            instr_file = tmp_path / "instructions.txt"
            instr_file.write_text(instructions)
            run = run_scan(
                target=task["target"],
                scan_mode=task["scan_mode"],
                max_budget_usd=task["max_budget_usd"],
                workdir=tmp_path,
                instruction_file=str(instr_file),
            )
            if run.run_dir is None:
                return 0.0, {"error": "no run dir", "covered": 0, "total": len(categories)}
            score = score_findings(load_findings(run.run_dir), categories)
        return score.fraction, score.to_dict()

    return rollout


def feedback(breakdown: dict[str, Any]) -> str:
    missed = breakdown.get("missed", [])
    covered = breakdown.get("covered", [])
    if not missed:
        return f"Covered every category ({covered}). The instruction is working well."
    return (
        f"Covered {breakdown.get('categories_covered', 0)}/"
        f"{breakdown.get('categories_total', 0)} categories. "
        f"Missed: {', '.join(missed)}. "
        "Revise the instruction so the agent deliberately looks for the missed "
        "classes of vulnerability on this kind of web application. Keep it general "
        "and reusable; do not hard-code answers or add any identifying markers."
    )


class JiteraGEPAAdapter(GEPAAdapter):
    """Scores instruction candidates by running the eval and reflects on misses."""

    def __init__(self, rollout: Rollout, component: str = COMPONENT) -> None:
        self._rollout = rollout
        self._component = component

    def evaluate(
        self,
        batch: list[dict[str, Any]],
        candidate: dict[str, str],
        capture_traces: bool = False,
    ) -> EvaluationBatch[dict[str, Any], dict[str, Any]]:
        instructions = candidate[self._component]
        outputs: list[dict[str, Any]] = []
        scores: list[float] = []
        trajectories: list[dict[str, Any]] | None = [] if capture_traces else None
        for task in batch:
            score, breakdown = self._rollout(instructions, task)
            outputs.append(breakdown)
            scores.append(score)
            if trajectories is not None:
                trajectories.append(
                    {"task": task, "instructions": instructions, "breakdown": breakdown}
                )
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(
        self,
        candidate: dict[str, str],  # noqa: ARG002  (required by GEPAAdapter)
        eval_batch: EvaluationBatch[dict[str, Any], dict[str, Any]],
        components_to_update: list[str],
    ) -> Mapping[str, Sequence[Mapping[str, Any]]]:
        trajectories = eval_batch.trajectories or []
        dataset: dict[str, list[dict[str, Any]]] = {}
        for component in components_to_update:
            records: list[dict[str, Any]] = []
            for traj in trajectories:
                breakdown = traj["breakdown"]
                records.append(
                    {
                        "Inputs": f"Scan target of type: {traj['task'].get('baseline')}",
                        "Generated Outputs": (
                            f"Covered categories: {breakdown.get('covered', [])}"
                        ),
                        "Feedback": feedback(breakdown),
                    }
                )
            dataset[component] = records
        return dataset
