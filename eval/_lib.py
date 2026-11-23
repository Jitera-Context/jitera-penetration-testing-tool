"""Shared helpers: load the baseline, locate paths, record run results."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml

from eval.score import Category
from strix.config import load_settings
from strix.config.loader import apply_config_override
from strix.jitera import bootstrap, brand


MISSING_MODEL_HELP = (
    "No LLM model configured. Copy .env.example to .env and set JITERA_PENTEST_LLM "
    "and LLM_API_KEY (or export them in your shell)."
)

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
    """Findings for scoring, from ``vulnerabilities.json`` or, if that is absent,
    ``findings.sarif``.

    The engine writes ``findings.sarif`` continuously but ``vulnerabilities.json``
    only at certain points, so a scan stopped at a timeout often has the SARIF but
    not the JSON. Falling back to the SARIF lets a partial run still be scored
    instead of crashing the eval.
    """
    path = run_dir / "vulnerabilities.json"
    if path.is_file():
        data = json.loads(path.read_text())
        if not isinstance(data, list):
            msg = f"{path} is not a list of findings"
            raise TypeError(msg)
        return data
    sarif = run_dir / "findings.sarif"
    if sarif.is_file():
        return _findings_from_sarif(sarif)
    msg = f"no vulnerabilities.json or findings.sarif in {run_dir} (did the scan start?)"
    raise FileNotFoundError(msg)


def _findings_from_sarif(path: Path) -> list[dict[str, Any]]:
    """Extract scoreable findings (title, description, cwe) from a SARIF report."""
    sarif = json.loads(path.read_text())
    findings: list[dict[str, Any]] = []
    for run in sarif.get("runs", []):
        rules = {r.get("id"): r for r in run.get("tool", {}).get("driver", {}).get("rules", [])}
        for res in run.get("results", []):
            rule = rules.get(res.get("ruleId"), {})
            tags = " ".join(
                rule.get("properties", {}).get("tags", [])
                + res.get("properties", {}).get("tags", [])
            )
            cwe = re.search(r"cwe-(\d+)", tags, re.IGNORECASE)
            findings.append(
                {
                    "title": rule.get("name") or res.get("ruleId", ""),
                    "cwe": f"CWE-{cwe.group(1)}" if cwe else None,
                    "description": res.get("message", {}).get("text", "")
                    + " "
                    + rule.get("fullDescription", {}).get("text", ""),
                }
            )
    return findings


def utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def record_result(record: dict[str, Any]) -> Path:
    """Write one run's result and keep latest.json + an append-only history."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    stamp = record.get("timestamp") or utc_stamp()
    out = RESULTS_DIR / f"{stamp}.json"
    suffix = 1
    while out.exists():  # two runs in the same second must not overwrite each other
        out = RESULTS_DIR / f"{stamp}-{suffix}.json"
        suffix += 1
    out.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    (RESULTS_DIR / "latest.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    with (RESULTS_DIR / "history.jsonl").open("a") as history:
        history.write(json.dumps(record, sort_keys=True) + "\n")
    return out


def prepare_settings() -> None:
    """Use the same settings as the scans: our .env, then JITERA_PENTEST_* -> STRIX_*.

    Call once, before reading any setting: ``load_settings`` is memoized.
    """
    bootstrap.load_env_file()
    bootstrap.prepare_environment(os.environ, brand.JITERA)
    # The scans run as Jitera, so read the settings file they read.
    bootstrap.copy_upstream_settings()
    apply_config_override(Path.home() / brand.JITERA.home_dir_name / "cli-config.json")


def configured_model() -> str | None:
    """The model a scan will use: shell, then .env, then ~/.jitera-pentest/cli-config.json."""
    model = (load_settings().llm.model or "").strip()
    return model or None
