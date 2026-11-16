"""What Jitera writes to disk (runs, logs, temp and settings folders) is named after Jitera."""

from __future__ import annotations

import ast
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import pytest

from strix.jitera import bootstrap, brand
from strix.telemetry.logging import setup_scan_logging


ROOT = Path(__file__).resolve().parents[2]


def test_jitera_output_names() -> None:
    assert brand.JITERA.home_dir_name == ".jitera-pentest"
    assert brand.JITERA.runs_dir_name == "jitera_pentest_runs"
    assert brand.JITERA.log_file_name == "jitera_pentest.log"
    assert brand.JITERA.temp_dir_name("repos") == "jitera_pentest_repos"


def test_upstream_output_names_are_unchanged() -> None:
    assert brand.UPSTREAM.home_dir_name == ".strix"
    assert brand.UPSTREAM.runs_dir_name == "strix_runs"
    assert brand.UPSTREAM.log_file_name == "strix.log"
    assert brand.UPSTREAM.temp_dir_name("repos") == "strix_repos"


# Every file kept under the home folder, as (module, attribute).
HOME_FILES = [
    ("strix.config.loader", "_DEFAULT_PATH"),
    ("strix.config.codex", "AUTH_PATH"),
    ("strix.tools.mcp.loader", "_DEFAULT_PATH"),
    ("strix.interface.viewer.auth", "AUTH_PATH"),
    ("strix.interface.platform_cli", "AUTH_PATH"),
    ("strix.interface.platform_identity", "IDENTITY_PATH"),
    ("strix.interface.update_check", "_CACHE_PATH"),
]


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_home_folder_follows_the_brand(profile: str) -> None:
    code = (
        "import importlib, json\n"
        "from strix.jitera import brand\n"
        f"brand.activate(brand.{profile})\n"
        f"files = {HOME_FILES!r}\n"
        "print(json.dumps(sorted({str(getattr(importlib.import_module(m), a).parent)"
        " for m, a in files})))\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    expected = str(Path.home() / getattr(brand, profile).home_dir_name)
    assert json.loads(result.stdout) == [expected]


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_runs_folder_follows_the_brand(profile: str) -> None:
    # A fresh interpreter, because the folder name is fixed when strix.core.paths loads.
    code = (
        "from strix.jitera import brand\n"
        f"brand.activate(brand.{profile})\n"
        "from strix.core import paths\n"
        "print(paths.runs_base_dir().name)\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=True, timeout=120
    )
    assert result.stdout.strip() == getattr(brand, profile).runs_dir_name


def test_scan_log_is_named_after_jitera(tmp_path: Path) -> None:
    brand.activate(brand.JITERA)
    setup_scan_logging(tmp_path)()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["jitera_pentest.log"]


def test_temp_staging_is_named_after_jitera(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from strix.interface.utils import write_fetched_collection  # noqa: PLC0415

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    brand.activate(brand.JITERA)
    path = Path(write_fetched_collection({"info": {}}, "abc"))
    assert path.relative_to(tmp_path).parts[0] == "jitera_pentest_api_specs"


def test_help_points_resume_at_the_jitera_runs_folder(tmp_path: Path) -> None:
    # A throwaway home: the command copies settings from ~/.strix on first run.
    result = subprocess.run(
        [sys.executable, "-m", "strix.jitera", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert "./jitera_pentest_runs/" in result.stdout
    assert "~/.jitera-pentest/cli-config.json" in result.stdout
    assert "~/.jitera-pentest/mcp-servers.json" in result.stdout
    assert "strix_runs" not in result.stdout
    assert ".strix" not in result.stdout


# Paths that would put a Strix name on the user's disk.
_STRIX_PATH = re.compile(
    r"^\.strix(/|$)|~/\.strix\b|\bstrix_(runs|repos|api_specs)\b|\bstrix\.log\b"
)


def _docstrings(tree: ast.AST) -> set[int]:
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
                found.add(id(body[0].value))
    return found


def test_upstream_code_names_no_disk_path_after_strix() -> None:
    """Catches a Strix-named folder or file that a sync brings in.

    Fix a hit the same way as the others: read the name from the brand.
    """
    hits: list[str] = []
    for path in sorted((ROOT / "strix").rglob("*.py")):
        if "jitera" in path.relative_to(ROOT).parts:
            continue
        hits.extend(
            f"{path.relative_to(ROOT)}:{line}: {text!r}" for line, text in _strix_paths(path)
        )
    assert hits == []


def _strix_paths(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    skip = _docstrings(tree)
    return [
        (node.lineno, node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in skip
        and _STRIX_PATH.search(node.value)
    ]


def test_the_guard_catches_the_names_upstream_uses(tmp_path: Path) -> None:
    sample = tmp_path / "sample.py"
    sample.write_text(
        '"""Docstrings may say ~/.strix."""\n'
        'HOME = Path.home() / ".strix" / "x.json"\n'
        'RUNS = "strix_runs"\n'
        'LOG = run_dir / "strix.log"\n'
        'HELP = f"edit ~/.strix/cli-config.json for {x}"\n'
        'IGNORE = ".strixignore"\n'
    )
    assert sorted(line for line, _ in _strix_paths(sample)) == [2, 3, 4, 5]


def _private(path: Path) -> bool:
    return stat.S_IMODE(path.stat().st_mode) == 0o600


def test_settings_are_copied_from_strix_once(tmp_path: Path) -> None:
    old = tmp_path / ".strix"
    old.mkdir()
    (old / "cli-config.json").write_text('{"env": {"STRIX_LLM": "x"}}')
    (old / "mcp-servers.json").write_text("[]")
    (old / "subscription-auth.json").write_text("{}")

    assert bootstrap.copy_upstream_settings(tmp_path) == ["cli-config.json", "mcp-servers.json"]
    new = tmp_path / ".jitera-pentest"
    assert sorted(p.name for p in new.iterdir()) == ["cli-config.json", "mcp-servers.json"]
    assert (new / "cli-config.json").read_text() == '{"env": {"STRIX_LLM": "x"}}'
    assert _private(new / "cli-config.json")
    assert _private(new / "mcp-servers.json")
    assert (old / "cli-config.json").exists()  # the original stays for upstream Strix

    (old / "cli-config.json").write_text("changed later")
    assert bootstrap.copy_upstream_settings(tmp_path) == []
    assert (new / "cli-config.json").read_text() == '{"env": {"STRIX_LLM": "x"}}'


def test_nothing_is_created_without_upstream_settings(tmp_path: Path) -> None:
    assert bootstrap.copy_upstream_settings(tmp_path) == []
    (tmp_path / ".strix").mkdir()
    (tmp_path / ".strix" / "viewer-auth.json").write_text("{}")
    assert bootstrap.copy_upstream_settings(tmp_path) == []
    assert not (tmp_path / ".jitera-pentest").exists()


def test_existing_jitera_settings_are_never_overwritten(tmp_path: Path) -> None:
    (tmp_path / ".strix").mkdir()
    (tmp_path / ".strix" / "cli-config.json").write_text("upstream")
    (tmp_path / ".jitera-pentest").mkdir()
    assert bootstrap.copy_upstream_settings(tmp_path) == []
    assert not (tmp_path / ".jitera-pentest" / "cli-config.json").exists()


@pytest.mark.parametrize("profile", ["UPSTREAM", "JITERA"])
def test_version_names_the_command(profile: str) -> None:
    code = (
        "import sys\n"
        "from strix.jitera import brand\n"
        f"brand.activate(brand.{profile})\n"
        "from strix.interface.cli_args import parse_arguments\n"
        "sys.argv = ['x', '--version']\n"
        "parse_arguments()\n"
    )
    result = subprocess.run(  # noqa: S603
        [sys.executable, "-c", code], capture_output=True, text=True, check=False, timeout=120
    )
    assert result.stdout.split()[0] == getattr(brand, profile).command


def test_the_package_installs_only_the_jitera_command() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    assert project["scripts"] == {"jitera-pentest": "strix.jitera.bootstrap:main"}
