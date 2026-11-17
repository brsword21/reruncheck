import json
import sys

import pytest
from test_snapshot import cli


@pytest.mark.parametrize("failed_run", [1, 2])
def test_nonzero_exit_is_error_with_post_failure_observation(tmp_path, failed_run):
    script = (
        "from pathlib import Path; import sys; p=Path('count'); "
        "n=int(p.read_text())+1 if p.exists() else 1; p.write_text(str(n)); "
        f"sys.exit(7 if n=={failed_run} else 0)"
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
    assert result.returncode == 2
    doc = json.loads(result.stdout)
    assert doc["outcome"] == "error"
    assert doc["converged"] is None
    assert len(doc["commands"]) == failed_run
    assert doc["commands"][-1]["returncode"] == 7
    name = "first" if failed_run == 1 else "second"
    assert doc["errors"][0]["phase"] == "run_" + name
    assert doc["errors"][0]["code"] == "nonzero_exit"
    assert doc["observations"]["after_" + name]["entries"][0]["path"] == "count"
    assert list(tmp_path.iterdir()) == []


def test_process_and_observation_failures_are_both_preserved(tmp_path):
    script = "import os,sys; os.mkfifo('fifo'); sys.exit(9)"
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
    doc = json.loads(result.stdout)
    assert result.returncode == 2
    assert doc["commands"][0]["returncode"] == 9
    assert [e["phase"] for e in doc["errors"]] == ["run_first", "after_first"]
    assert doc["converged"] is None


@pytest.mark.parametrize("budget", ["--timeout", "--max-output-bytes"])
@pytest.mark.parametrize("value", ["0", "-1", "nan", "999999999999"])
def test_invalid_execution_budgets_never_launch(tmp_path, budget, value):
    marker = tmp_path / "no"
    script = f"open({str(marker)!r},'w').close()"
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--json",
        budget,
        value,
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["commands"] == []
    assert not marker.exists()
