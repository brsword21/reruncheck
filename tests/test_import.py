import copy
import json
import os

import pytest
from test_snapshot import cli


@pytest.mark.parametrize(
    "damage",
    [
        "version",
        "version_bool",
        "kind",
        "mode_bool",
        "size_string",
        "digest",
        "extra",
        "absolute",
        "dotdot",
        "dot",
        "double_slash",
        "backslash",
        "duplicate_path",
        "duplicate_key",
        "parent_file",
        "missing_parent",
        "coverage",
        "ignore_type",
        "excluded_type",
        "nan",
        "invalid_json",
        "scalar",
        "too_large",
        "fifo",
    ],
)
def test_import_rejects_malformed_snapshots(tmp_path, damage):
    root = tmp_path / "tree"
    root.mkdir()
    (root / "file").write_text("x")
    good = json.loads(cli("snapshot", root).stdout)
    doc = copy.deepcopy(good)
    entry = doc["entries"][0]
    changes = {
        "version": lambda: doc.update(schema_version=2),
        "version_bool": lambda: doc.update(schema_version=True),
        "kind": lambda: entry.update(kind="socket"),
        "mode_bool": lambda: entry.update(mode=True),
        "size_string": lambda: entry.update(size="1"),
        "digest": lambda: entry.update(sha256="not-a-digest"),
        "extra": lambda: entry.update(target="impossible"),
        "absolute": lambda: entry.update(path="/etc/passwd"),
        "dotdot": lambda: entry.update(path="../escape"),
        "dot": lambda: entry.update(path="./file"),
        "double_slash": lambda: entry.update(path="a//b"),
        "backslash": lambda: entry.update(path="..\\escape"),
        "duplicate_path": lambda: doc["entries"].append(copy.deepcopy(entry)),
        "parent_file": lambda: doc["entries"].append(dict(entry, path="file/child")),
        "missing_parent": lambda: entry.update(path="missing/child"),
        "coverage": lambda: doc["coverage"].update(not_compared=[]),
        "ignore_type": lambda: doc["coverage"].update(ignore_patterns=False),
        "excluded_type": lambda: doc["coverage"].update(excluded_paths=[False]),
        "nan": lambda: entry.update(size=float("nan")),
    }
    if damage in changes:
        changes[damage]()
    bad, valid = tmp_path / "bad.json", tmp_path / "good.json"
    raw = json.dumps(doc)
    if damage == "duplicate_key":
        raw = raw.replace('"schema_version": 1', '"schema_version": 1, "schema_version": 1')
    elif damage == "invalid_json":
        raw = "{"
    elif damage == "scalar":
        raw = "null"
    elif damage == "too_large":
        raw = " " * 4097
    valid.write_text(json.dumps(good))
    if damage == "fifo":
        os.mkfifo(bad)
    else:
        bad.write_text(raw)
    budget = ["--max-json-bytes", "4096"] if damage == "too_large" else []
    result = cli("compare", bad, valid, "--json", *budget)
    assert result.returncode == 2, result.stdout
    assert json.loads(result.stdout)["outcome"] == "error"
    assert "Traceback" not in result.stderr
    if damage == "too_large":
        assert "max_json_bytes" in json.loads(result.stdout)["errors"][0]["message"]


def test_different_ignore_policy_cannot_be_labelled_equal(tmp_path):
    root = tmp_path / "tree"
    root.mkdir()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(cli("snapshot", root).stdout)
    b.write_text(cli("snapshot", root, "--ignore", "*.secret").stdout)
    result = cli("compare", a, b, "--json")
    assert result.returncode == 2
