import json
import os

import pytest
from test_snapshot import cli


def save_snapshot(root, output):
    result = cli("snapshot", root)
    assert result.returncode == 0, result.stdout
    output.write_text(result.stdout)


@pytest.mark.parametrize(
    "mutation,reasons",
    [
        ("same", []),
        ("timestamp", []),
        ("content", ["content"]),
        ("mode", ["mode"]),
        ("both", ["content", "mode"]),
        ("remove", ["removed"]),
        ("add", ["added"]),
        ("kind", ["kind", "mode"]),
        ("target", ["target"]),
    ],
)
def test_compare_reasons(tmp_path, mutation, reasons):
    root = tmp_path / "tree"
    root.mkdir()
    path = root / "x"
    if mutation == "target":
        path.symlink_to("one")
    else:
        path.write_text("old")
    before, after = tmp_path / "before.json", tmp_path / "after.json"
    save_snapshot(root, before)
    if mutation in ("content", "both"):
        path.write_text("new")
    if mutation in ("mode", "both"):
        path.chmod(0o600)
    if mutation == "remove":
        path.unlink()
    if mutation == "add":
        (root / "added").mkdir()
    if mutation == "kind":
        path.unlink()
        path.mkdir()
    if mutation == "target":
        path.unlink()
        path.symlink_to("two")
    if mutation == "timestamp":
        os.utime(path, (1, 1))
    save_snapshot(root, after)
    result = cli("compare", before, after, "--json")
    assert result.returncode == bool(reasons), result.stdout
    report = json.loads(result.stdout)
    assert report["outcome"] == ("different" if reasons else "equal")
    assert report["changes"] == (
        [{"path": "added" if mutation == "add" else "x", "reasons": reasons}] if reasons else []
    )
    human = cli("compare", before, after)
    assert human.returncode == result.returncode
    assert report["outcome"] in human.stdout
