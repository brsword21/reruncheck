import json
import sys

import pytest
from test_snapshot import cli

from reruncheck.limits import Limits, ReruncheckError
from reruncheck.snapshot import snapshot


def test_entry_and_byte_limits_accept_exact_boundary_but_bound_aggregate(tmp_path):
    (tmp_path / "one").write_bytes(b"123")
    assert len(snapshot(tmp_path, limits=Limits(max_entries=1, max_bytes=3)).entries) == 1
    (tmp_path / "two").write_bytes(b"456")
    with pytest.raises(ReruncheckError, match="max_bytes"):
        snapshot(tmp_path, limits=Limits(max_bytes=5))


def test_snapshot_never_reads_actual_external_symlink_contents(tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "large").write_bytes(b"secret" * 1000)
    root = tmp_path / "fixture"
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    state = snapshot(root, limits=Limits(max_bytes=1, max_entries=1))
    assert len(state.entries) == 1
    assert state.entries[0].target == str(outside)
    assert state.entries[0].sha256 is None


def test_missing_expected_state_is_preflight_error_without_execution(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    marker = tmp_path / "marker"
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--expect",
        tmp_path / "missing",
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        f"open({str(marker)!r},'w').close()",
    )
    doc = json.loads(result.stdout)
    assert result.returncode == 2
    assert doc["first_run_asserted"] is True
    assert doc["first_run_matches"] is None
    assert doc["commands"] == []
    assert doc["errors"][0]["phase"] == "preflight"
    assert not marker.exists()


def test_second_successful_command_can_still_make_observation_incomplete(tmp_path):
    script = (
        "from pathlib import Path; import os; p=Path('count'); "
        "n=int(p.read_text())+1 if p.exists() else 1; p.write_text(str(n)); "
        "os.mkfifo('fifo') if n==2 else None"
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
    doc = json.loads(result.stdout)
    assert result.returncode == 2
    assert doc["converged"] is None
    assert [c["returncode"] for c in doc["commands"]] == [0, 0]
    assert doc["errors"][0]["phase"] == "after_second"
    assert "after_first" in doc["observations"]
    assert "after_second" not in doc["observations"]


def test_relative_fixture_script_executes_in_copy(tmp_path):
    (tmp_path / "normalize.py").write_text(
        "from pathlib import Path; Path('data').write_text('ok')"
    )
    before = snapshot(tmp_path)
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "normalize.py",
    )
    assert result.returncode == 0, result.stdout
    assert snapshot(tmp_path) == before
    assert not (tmp_path / "data").exists()
