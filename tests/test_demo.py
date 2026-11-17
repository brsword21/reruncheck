import json

import pytest
from test_snapshot import cli


@pytest.mark.parametrize("case,code", [("stable", 0), ("broken", 1)])
def test_authored_demo_uses_expected_first_state_and_real_two_runs(case, code):
    result = cli("demo", "--case", case, "--json")
    assert result.returncode == code, result.stdout
    doc = json.loads(result.stdout)
    assert doc["first_run_asserted"] is True
    assert doc["first_run_matches"] is True
    assert doc["converged"] is (case == "stable")
    assert doc["outcome"] == ("converged" if case == "stable" else "nonconvergent")
    assert [c["returncode"] for c in doc["commands"]] == [0, 0]
    assert [c["path"] for c in doc["changes"]] == ([] if case == "stable" else ["data.txt"])
    human = cli("demo", "--case", case)
    assert human.returncode == code
    assert doc["outcome"] in human.stdout
    assert "first_run_matches: true" in human.stdout
    assert "not an OS sandbox" in human.stdout


def test_human_execution_errors_go_to_stderr(tmp_path):
    result = cli("check", "--fixture", tmp_path, "--trust-command", "--", "not-a-real-command")
    assert result.returncode == 2
    assert not result.stdout
    assert "run_first" in result.stderr
    assert "Traceback" not in result.stderr
