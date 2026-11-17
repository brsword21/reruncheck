import hashlib
import json
import os
import subprocess
import sys


def cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "reruncheck", *map(str, args)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )


def test_snapshot_cli_includes_empty_hidden_links_and_digest(tmp_path):
    (tmp_path / ".hidden").write_bytes(b"hello")
    (tmp_path / ".hidden").chmod(0o644)
    (tmp_path / "empty").mkdir()
    (tmp_path / "link").symlink_to("outside")
    result = cli("snapshot", tmp_path)
    assert result.returncode == 0, result.stderr
    doc = json.loads(result.stdout)
    assert doc["schema_version"] == 1
    entries = {e["path"]: e for e in doc["entries"]}
    assert list(entries) == [".hidden", "empty", "link"]
    assert entries[".hidden"] == {
        "path": ".hidden",
        "kind": "file",
        "mode": 0o644,
        "size": 5,
        "sha256": hashlib.sha256(b"hello").hexdigest(),
    }
    assert entries["empty"]["kind"] == "directory"
    assert entries["link"]["target"] == "outside"
    assert entries["link"]["kind"] == "symlink"
    assert "mtime" in doc["coverage"]["not_compared"]
    assert os.path.islink(tmp_path / "link")
