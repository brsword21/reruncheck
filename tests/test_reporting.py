import json
import sys

from test_snapshot import cli


def test_report_budget_error_preserves_actual_command_receipts(tmp_path):
    for index in range(4):
        (tmp_path / (str(index) + "x" * 40)).touch()
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--json",
        "--max-json-bytes",
        "4096",
        "--",
        sys.executable,
        "-c",
        "pass",
    )
    assert result.returncode == 2
    doc = json.loads(result.stdout)
    assert doc["outcome"] == "error"
    assert doc["converged"] is None
    assert [c["returncode"] for c in doc["commands"]] == [0, 0]
    assert doc["errors"][-1]["phase"] == "report"
    assert doc["errors"][-1]["code"] == "report_limit"
    assert doc["report_truncated"] is True
    assert len(result.stdout.encode()) <= 4096


def test_expected_mismatch_human_output_includes_expected_diff(tmp_path):
    fixture, expected = tmp_path / "fixture", tmp_path / "expected"
    fixture.mkdir()
    expected.mkdir()
    (expected / "missing").touch()
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--expect",
        expected,
        "--trust-command",
        "--",
        sys.executable,
        "-c",
        "pass",
    )
    assert result.returncode == 1
    assert "expected missing: removed" in result.stdout


def test_compare_and_demo_reject_unused_ignore_options(tmp_path):
    source = tmp_path / "tree"
    source.mkdir()
    document = tmp_path / "snapshot.json"
    document.write_text(cli("snapshot", source).stdout)
    for args in [("compare", document, document), ("demo", "--case", "stable")]:
        result = cli(*args, "--ignore", "*", "--json")
        assert result.returncode == 2
        assert json.loads(result.stdout)["outcome"] == "error"
