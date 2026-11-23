"""Run one scan of the target and locate its output directory.

The scan runs the Jitera entry point (``python -m strix.jitera``) headlessly in
a fresh working directory, so the single run it produces under ``jitera_pentest_runs/`` is
unambiguous without needing a run-name flag.
"""

from __future__ import annotations

import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import TYPE_CHECKING

from strix.jitera import brand


if TYPE_CHECKING:
    from pathlib import Path


SCAN_ENTRY = [sys.executable, "-m", "strix.jitera"]


def build_command(
    target: str,
    scan_mode: str,
    max_budget_usd: float,
    instruction_file: str | None = None,
) -> list[str]:
    """The headless scan command. Pure, so it can be asserted in tests."""
    cmd = [
        *SCAN_ENTRY,
        "-n",  # always headless for the eval
        "--target",
        target,
        "--scan-mode",
        scan_mode,
        "--max-budget",
        str(max_budget_usd),
    ]
    if instruction_file:
        cmd += ["--instruction-file", instruction_file]
    return cmd


def check_reachable(url: str, timeout: float = 10.0) -> tuple[bool, str]:
    """Return (ok, detail). The live Juice Shop demo is often down (503)."""
    request = urllib.request.Request(url, method="GET")  # noqa: S310  (fixed https target)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            code = response.status
            return (200 <= code < 400, f"HTTP {code}")
    except urllib.error.HTTPError as exc:
        return (exc.code < 500, f"HTTP {exc.code}")
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return (False, f"unreachable: {exc}")


def find_run_dir(workdir: Path) -> Path | None:
    """The newest run directory the Jitera entry point produced under ``workdir``."""
    runs = workdir / brand.JITERA.runs_dir_name
    if not runs.is_dir():
        return None
    candidates = [d for d in runs.iterdir() if d.is_dir()]
    if not candidates:
        return None
    return max(candidates, key=lambda d: d.stat().st_mtime)


@dataclass(frozen=True)
class RunResult:
    run_dir: Path | None
    exit_code: int | None  # None when the scan was stopped at the timeout
    stdout: str
    stderr: str


def run_scan(
    target: str,
    scan_mode: str,
    max_budget_usd: float,
    workdir: Path,
    instruction_file: str | None = None,
    timeout_s: float = 60 * 60 * 4,
) -> RunResult:
    """Run one headless scan in ``workdir`` and return where it wrote results.

    A scan that overruns ``timeout_s`` is killed, but its run directory is still
    returned and scored: the engine writes ``vulnerabilities.json`` continuously,
    so the partial run is the real coverage so far, not a zero. The exit code is
    then ``None``. This matters for GEPA, where a long scan would otherwise crash
    the whole optimization instead of scoring what it found.
    """
    workdir.mkdir(parents=True, exist_ok=True)
    cmd = build_command(target, scan_mode, max_budget_usd, instruction_file)
    try:
        completed = subprocess.run(  # noqa: S603  (fixed argv, no shell)
            cmd,
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return RunResult(
            run_dir=find_run_dir(workdir),
            exit_code=None,
            stdout=exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
            stderr=(exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
            + f"\n[eval] scan exceeded {timeout_s:.0f}s and was stopped; scoring the partial run.",
        )
    return RunResult(
        run_dir=find_run_dir(workdir),
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )
