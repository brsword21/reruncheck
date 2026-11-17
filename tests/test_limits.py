import json
import os

import pytest
from test_snapshot import cli


@pytest.mark.parametrize(
    "case", ["bytes", "entries", "fifo", "missing", "root_link", "zero", "unreadable"]
)
def test_snapshot_errors_are_structured_not_partial(tmp_path, case):
    root = tmp_path / "tree"
    root.mkdir()
    args = []
    if case == "bytes":
        (root / "x").write_bytes(b"12345")
        args = ["--max-bytes", "4"]
    elif case == "entries":
        (root / "x").touch()
        (root / "y").touch()
        args = ["--max-entries", "1"]
    elif case == "fifo":
        os.mkfifo(root / "fifo")
    elif case == "missing":
        root = root / "missing"
    elif case == "root_link":
        (tmp_path / "alias").symlink_to(root, target_is_directory=True)
        root = tmp_path / "alias"
    elif case == "zero":
        args = ["--max-bytes", "0"]
    else:
        (root / "private").write_text("secret")
        (root / "private").chmod(0)
    result = cli("snapshot", root, "--json", *args)
    assert result.returncode == 2
    report = json.loads(result.stdout)
    assert report["outcome"] == "error"
    assert report["errors"][0]["phase"] == "snapshot"
    assert "Traceback" not in result.stderr


def test_ignore_is_explicit_with_subtree_coverage(tmp_path):
    (tmp_path / "skip").mkdir()
    (tmp_path / "skip" / "private").write_text("excluded")
    (tmp_path / ".keep").touch()
    result = cli("snapshot", tmp_path, "--ignore", "skip")
    assert result.returncode == 0
    doc = json.loads(result.stdout)
    assert [e["path"] for e in doc["entries"]] == [".keep"]
    assert doc["coverage"]["ignore_patterns"] == ["skip"]
    assert doc["coverage"]["excluded_paths"] == ["skip"]
