import json
import sys

import pytest
from test_snapshot import cli


def test_argv_is_literal_including_empty_and_shell_metacharacters(tmp_path):
    arguments = ["", "$HOME", "~", "*", ";touch unexpected", "--json"]
    script = f"import sys; assert sys.argv[1:] == {arguments!r}"
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--",
        sys.executable,
        "-c",
        script,
        *arguments,
    )
    assert result.returncode == 0, (result.stdout, result.stderr)
    assert result.stdout.startswith("converged\n")
    assert list(tmp_path.iterdir()) == []


def test_usage_error_never_echoes_secret_command_arguments(tmp_path):
    secret = "SYNTHETIC_SECRET_DO_NOT_REPORT"
    result = cli(
        "check", "--fixture", tmp_path, "--trust-command", "--json", sys.executable, "-c", secret
    )
    assert result.returncode == 2
    assert secret not in result.stdout + result.stderr
    assert json.loads(result.stdout)["outcome"] == "error"


def test_forwarded_environment_is_narrow_and_only_names_are_reported(tmp_path, monkeypatch):
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "SECRET_TOKEN_DO_NOT_REPORT")
    monkeypatch.setenv("RERUNCHECK_TEST_PRIVATE", "SECRET_TOKEN_DO_NOT_REPORT")
    script = (
        "import os; assert 'AWS_SECRET_ACCESS_KEY' not in os.environ; "
        "assert 'RERUNCHECK_TEST_PRIVATE' not in os.environ; assert 'PATH' in os.environ"
    )
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == 0
    doc = json.loads(result.stdout)
    assert set(doc["environment_forwarded"]) <= {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "TMPDIR",
    }
    assert "PATH" in doc["environment_forwarded"]
    assert doc["limits"]["timeout"] == 10.0
    assert doc["limits"]["max_output_bytes"] == 1048576
    assert "SECRET_TOKEN" not in result.stdout


@pytest.mark.parametrize("name", ["..\\escape", "C:drive"])
def test_snapshot_rejects_names_that_cannot_roundtrip_safe_import(tmp_path, name):
    (tmp_path / name).touch()
    result = cli("snapshot", tmp_path)
    assert result.returncode == 2
    assert json.loads(result.stdout)["outcome"] == "error"
