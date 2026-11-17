import json
import sys

import pytest
from test_snapshot import cli


@pytest.mark.parametrize("stable", [True, False])
def test_check_observes_two_runs_in_copy_not_source(tmp_path, stable):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "data").write_text("original")
    script = (
        "import sys; print('receipt'); print('notice', file=sys.stderr); "
        "from pathlib import Path; p=Path('data'); "
        + ("p.write_text('normalized')" if stable else "p.write_text(p.read_text()+'!')")
    )
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == (0 if stable else 1), result.stdout
    report = json.loads(result.stdout)
    assert report["outcome"] == ("converged" if stable else "nonconvergent")
    assert report["converged"] is stable
    assert report["first_run_asserted"] is False
    assert report["first_run_matches"] is None
    assert [r["returncode"] for r in report["commands"]] == [0, 0]
    assert [(r["stdout_bytes"], r["stderr_bytes"]) for r in report["commands"]] == [(8, 7)] * 2
    assert "receipt" not in result.stdout
    assert "notice" not in result.stdout
    assert set(report["observations"]) == {"original", "after_first", "after_second"}
    assert (fixture / "data").read_text() == "original"
    assert report["changes"] == ([] if stable else [{"path": "data", "reasons": ["content"]}])
    from reruncheck.runner import check

    library = check(fixture, [sys.executable, "-c", script], trust_command=True)
    assert library.converged is stable
    assert library.exit_code == result.returncode


@pytest.mark.parametrize(
    "content,append,expected_outcome,converged,matches",
    [
        ("right", False, "converged", True, True),
        ("wrong", False, "first_run_mismatch", True, False),
        ("right", True, "nonconvergent", False, True),
        ("wrong", True, "first_run_mismatch", False, False),
    ],
)
def test_expected_first_state_is_independent_of_convergence(
    tmp_path, content, append, expected_outcome, converged, matches
):
    fixture, expected = tmp_path / "fixture", tmp_path / "expected"
    fixture.mkdir()
    expected.mkdir()
    (expected / "data").write_text("right")
    script = "from pathlib import Path; p=Path('data'); " + (
        f"p.write_text(p.read_text()+'!' if p.exists() else {content!r})"
        if append
        else f"p.write_text({content!r})"
    )
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--expect",
        expected,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == (0 if expected_outcome == "converged" else 1), result.stdout
    report = json.loads(result.stdout)
    assert report["outcome"] == expected_outcome
    assert report["first_run_asserted"] is True
    assert report["first_run_matches"] is matches
    assert report["converged"] is converged
    assert bool(report["expected_changes"]) is not matches
    assert list(fixture.iterdir()) == []


@pytest.mark.parametrize("case", ["no_trust", "no_argv", "no_separator"])
def test_check_refuses_to_spawn_without_explicit_trust_and_argv(tmp_path, case):
    marker = tmp_path / "should-not-exist"
    command = [sys.executable, "-c", f"open({str(marker)!r},'w').close()"]
    args = ["check", "--fixture", tmp_path, "--json"]
    if case != "no_trust":
        args.append("--trust-command")
    if case != "no_argv":
        if case != "no_separator":
            args.append("--")
        args += command
    result = cli(*args)
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["first_run_asserted"] is False
    assert report["first_run_matches"] is None
    assert report["converged"] is None
    assert report["commands"] == []
    assert not marker.exists()
