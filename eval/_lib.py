"""Shared helpers: load the baseline, locate paths, record run results."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from eval.score import Category


EVAL_DIR = Path(__file__).resolve().parent
BASELINE_DIR = EVAL_DIR / "baseline"
RESULTS_DIR = EVAL_DIR / "results"


@dataclass(frozen=True)
class Baseline:
    name: str
    target: str
    min_categories: int
    scan_mode: str
    max_budget_usd: float
    categories: tuple[Category, ...]

    @classmethod
    def load(cls, name: str = "juice-shop") -> Baseline:
        path = BASELINE_DIR / f"{name}.yaml"
        data: dict[str, Any] = yaml.safe_load(path.read_text())
        categories = tuple(Category.from_dict(c) for c in data["categories"])
        if not categories:
            msg = f"baseline {path} lists no categories"
            raise ValueError(msg)
        min_categories = int(data.get("min_categories", len(categories)))
        if not 0 < min_categories <= len(categories):
            msg = f"min_categories must be 1..{len(categories)}, got {min_categories}"
            raise ValueError(msg)
        return cls(
            name=name,
            target=str(data["target"]),
            min_categories=min_categories,
            scan_mode=str(data.get("scan_mode", "standard")),
            max_budget_usd=float(data.get("max_budget_usd", 15)),
            categories=categories,
        )


def load_findings(run_dir: Path) -> list[dict[str, Any]]:
    """Read ``vulnerabilities.json`` from a completed run directory."""
    path = run_dir / "vulnerabilities.json"
    if not path.is_file():
        msg = f"no vulnerabilities.json in {run_dir} (did the scan finish?)"
        raise FileNotFoundError(msg)
    data = json.loads(path.read_text())
    if not isinstance(data, list):
        msg = f"{path} is not a list of findings"
        raise TypeError(msg)
    return data


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def record_result(record: dict[str, Any]) -> Path:
    """Write one run's result and keep latest.json + an append-only history."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = record.get("timestamp") or utc_stamp()
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    (RESULTS_DIR / "latest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    with (RESULTS_DIR / "history.jsonl").open("a") as history:
        history.write(json.dumps(record, sort_keys=True) + "\n")
    return out
