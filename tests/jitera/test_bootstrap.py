from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from strix.jitera import bootstrap, brand
from strix.jitera.commands import COMMANDS


if TYPE_CHECKING:
    from pathlib import Path


def test_jitera_variables_are_copied_to_strix_names() -> None:
    env = {"JITERA_LLM": "openai/gpt-x", "STRIX_IMAGE": "explicit"}
    bootstrap.prepare_environment(env)
    assert env["STRIX_LLM"] == "openai/gpt-x"
    assert env["STRIX_IMAGE"] == "explicit"


def test_defaults_never_override_explicit_values() -> None:
    env = {"STRIX_TELEMETRY": "1"}
    bootstrap.prepare_environment(env)
    assert env["STRIX_TELEMETRY"] == "1"
    assert env["STRIX_NO_UPDATE_CHECK"] == "1"


def test_telemetry_is_off_by_default() -> None:
    env: dict[str, str] = {}
    bootstrap.prepare_environment(env)
    assert env["STRIX_TELEMETRY"] == "0"


@pytest.mark.parametrize(
    ("argv", "blocked"),
    [
        (["cloud", "login"], True),
        (["-n", "-t", "./app", "--update"], True),
        (["-n", "-t", "./app"], False),
        ([], False),
    ],
)
def test_blocked_commands(argv: list[str], *, blocked: bool) -> None:
    assert (bootstrap.blocked_reason(argv) is not None) is blocked


def test_skills_dir_exists() -> None:
    skills: Path = bootstrap.SKILLS_DIR
    assert skills.is_dir()


def test_about_command_prints_active_brand(capsys: pytest.CaptureFixture[str]) -> None:
    brand.activate(brand.JITERA)
    assert COMMANDS["about"]([]) == 0
    assert brand.JITERA.name in capsys.readouterr().out


def test_about_rejects_arguments() -> None:
    assert COMMANDS["about"](["extra"]) == 2
