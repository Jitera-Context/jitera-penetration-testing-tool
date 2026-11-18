"""Claude Code cannot commit code without its patches.

The PreToolUse hook in .claude/settings.json runs `fork/dev verify --staged`
before every `git commit` Claude runs here, and blocks the commit (exit 2) when
what it records has code and fork/patches out of step. These tests run the real
hook and fork/dev in a throwaway fork: an "upstream" commit as the checkpoint,
then our tooling on top.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


pytestmark = pytest.mark.skipif(
    sys.platform == "win32" or shutil.which("jq") is None or shutil.which("git") is None,
    reason="the hook is a bash script that reads its input with jq",
)

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / ".claude/hooks/verify-patches-before-commit.sh"
SETTINGS = ROOT / ".claude/settings.json"


def _git(repo: Path, *args: str) -> str:
    env = {
        **os.environ,
        "GIT_AUTHOR_NAME": "test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
    }
    result = subprocess.run(  # noqa: S603
        ["git", "-C", str(repo), *args],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        env=env,
        timeout=60,
    )
    return result.stdout.strip()


@pytest.fixture
def fork(tmp_path: Path) -> Path:
    repo = tmp_path / "fork"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "app.py").write_text("print('upstream')\n")
    _git(repo, "add", "app.py")
    _git(repo, "commit", "-q", "-m", "upstream")
    checkpoint = _git(repo, "rev-parse", "HEAD")
    (repo / "fork").mkdir()
    shutil.copy2(ROOT / "fork/dev", repo / "fork/dev")
    (repo / "fork/CHECKPOINT").write_text(f"{checkpoint} upstream\n")
    (repo / "fork/patches").mkdir()
    _git(repo, "add", "fork")
    _git(repo, "commit", "-q", "-m", "fork tooling")
    return repo


def _hook(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)})
    return subprocess.run(  # noqa: S603
        [str(HOOK)], input=payload, capture_output=True, text=True, check=False, timeout=120
    )


def _fork_dev(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [str(repo / "fork/dev"), *args], capture_output=True, text=True, check=False, timeout=120
    )


def _fill_header(repo: Path) -> None:
    patch = repo / "fork/patches/app.py.patch"
    text = patch.read_text()
    text = text.replace("Title: TODO one line: what this patch changes", "Title: Jitera greeting")
    text = text.replace("Why: TODO why Jitera needs it", "Why: our product name")
    patch.write_text(text)
    _git(repo, "add", str(patch))


def test_settings_run_the_hook_before_every_bash_call() -> None:
    settings = json.loads(SETTINGS.read_text())
    hooks = [
        hook["command"]
        for entry in settings["hooks"]["PreToolUse"]
        if entry["matcher"] == "Bash"
        for hook in entry["hooks"]
    ]
    assert hooks == ['"$CLAUDE_PROJECT_DIR"/.claude/hooks/verify-patches-before-commit.sh']
    assert os.access(HOOK, os.X_OK)


def test_a_commit_needs_its_patch(fork: Path) -> None:
    (fork / "app.py").write_text("print('jitera')\n")
    _git(fork, "add", "app.py")

    blocked = _hook("git commit -m 'feat: greet as jitera'", fork)
    assert blocked.returncode == 2
    assert "app.py" in blocked.stderr
    assert "fork/dev save" in blocked.stderr

    assert _fork_dev(fork, "save").returncode == 0
    todo = _hook("git commit -m x", fork)
    assert todo.returncode == 2, "an edited upstream file needs a real Title/Why"
    assert "TODO header" in todo.stderr

    _fill_header(fork)
    assert _hook("git commit -m x", fork).returncode == 0


def test_a_patch_without_its_code_is_blocked(fork: Path) -> None:
    (fork / "app.py").write_text("print('jitera')\n")
    assert _fork_dev(fork, "save").returncode == 0
    _fill_header(fork)
    # The patch is staged, the code it records is not.
    assert _fork_dev(fork, "verify").returncode == 0, "the working tree alone looks fine"
    blocked = _hook("git commit -m x", fork)
    assert blocked.returncode == 2
    assert "app.py (patch no longer needed)" in blocked.stderr
    # `git commit -a` records the code too, so it passes.
    assert _hook("git commit -am x", fork).returncode == 0


@pytest.mark.parametrize(
    "command",
    [
        "git commit -m x",
        "cd {repo} && git commit -m x",
        "git -C {repo} commit -m x",
        "git add app.py && git commit -m x",
    ],
)
def test_every_way_to_commit_is_checked(fork: Path, tmp_path: Path, command: str) -> None:
    (fork / "app.py").write_text("print('jitera')\n")
    _git(fork, "add", "app.py")
    cwd = fork if command.startswith("git ") else tmp_path
    assert _hook(command.format(repo=fork), cwd).returncode == 2


def test_other_commands_and_repositories_pass(fork: Path, tmp_path: Path) -> None:
    (fork / "app.py").write_text("print('jitera')\n")
    _git(fork, "add", "app.py")
    assert _hook("git status", fork).returncode == 0
    assert _hook("echo 'git committed'", fork).returncode == 0

    other = tmp_path / "other"
    other.mkdir()
    _git(other, "init", "-q")
    assert _hook("git commit -m x", other).returncode == 0, "not a fork: no fork/dev"
