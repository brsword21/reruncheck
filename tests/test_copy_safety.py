import json
import sys
from pathlib import Path

import pytest
from test_snapshot import cli


@pytest.mark.parametrize("target", ["../outside", "/etc/passwd", "loop", "ignored_escape"])
def test_execution_rejects_all_source_symlink_escapes_even_if_ignored(tmp_path, target):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    link = fixture / "link"
    link.symlink_to("../outside" if target == "ignored_escape" else target)
    marker = tmp_path / "marker"
    args = ["--ignore", "link"] if target == "ignored_escape" else []
    script = f"open({str(marker)!r},'w').close()"
    if target == "loop":
        link.unlink()
        link.symlink_to("link")
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--trust-command",
        "--json",
        *args,
        "--",
        sys.executable,
        "-c",
        script,
    )
    assert result.returncode == 2, result.stdout
    doc = json.loads(result.stdout)
    assert doc["commands"] == []
    assert not marker.exists()
    assert link.is_symlink()
    assert cli("snapshot", fixture).returncode == 0


def test_relative_link_that_reenters_original_by_name_still_escapes_copy(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "file").write_text("original")
    (fixture / "link").symlink_to("../fixture/file")
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        "pass",
    )
    assert result.returncode == 2, result.stdout
    assert json.loads(result.stdout)["commands"] == []


def test_directory_alias_cannot_hide_escape_and_reentry(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "file").touch()
    (fixture / "alias").symlink_to(".")
    (fixture / "link").symlink_to("alias/../fixture/file")
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        "pass",
    )
    assert result.returncode == 2, result.stdout
    assert json.loads(result.stdout)["commands"] == []


def test_internal_symlink_is_preserved_without_modifying_source(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "file").write_text("original")
    (fixture / "link").symlink_to("file")
    result = cli(
        "check",
        "--fixture",
        fixture,
        "--trust-command",
        "--json",
        "--",
        sys.executable,
        "-c",
        "from pathlib import Path; Path('link').write_text('new')",
    )
    assert result.returncode == 0, result.stdout
    assert (fixture / "file").read_text() == "original"
    assert (fixture / "link").readlink() == Path("file")


def test_ignored_data_is_still_bounded_before_copy(tmp_path):
    (tmp_path / "huge").write_text("1234567890")
    result = cli(
        "check",
        "--fixture",
        tmp_path,
        "--trust-command",
        "--ignore",
        "huge",
        "--max-bytes",
        "1",
        "--json",
        "--",
        sys.executable,
        "-c",
        "pass",
    )
    assert result.returncode == 2
    assert json.loads(result.stdout)["commands"] == []


def test_temporary_directory_inside_fixture_is_refused(tmp_path, monkeypatch):
    import tempfile

    from reruncheck.runner import check

    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    report = check(tmp_path, [sys.executable, "-c", "pass"], trust_command=True)
    assert report.exit_code == 2
    assert report.commands == []
    assert list(tmp_path.iterdir()) == []
