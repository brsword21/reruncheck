import os
import sys
import tempfile

import pytest

from reruncheck.limits import ReruncheckError
from reruncheck.runner import check
from reruncheck.snapshot import snapshot


def test_cleanup_error_cannot_leave_success_outcome(tmp_path, monkeypatch):
    original_exit = tempfile.TemporaryDirectory.__exit__

    def exit_then_error(self, *args):
        original_exit(self, *args)
        raise OSError("synthetic cleanup failure")

    monkeypatch.setattr(tempfile.TemporaryDirectory, "__exit__", exit_then_error)
    result = check(tmp_path, [sys.executable, "-c", "pass"], trust_command=True)
    assert result.exit_code == 2
    assert result.outcome.value == "error"
    assert result.errors[-1].phase == "cleanup"


def test_root_replacement_during_traversal_is_incomplete(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    (root / "data").write_text("old")
    real_open = os.open
    changed = False

    def open_then_replace(path, flags, *args, **kwargs):
        nonlocal changed
        fd = real_open(path, flags, *args, **kwargs)
        if path == root and not changed:
            changed = True
            root.rename(tmp_path / "moved")
            root.mkdir()
        return fd

    monkeypatch.setattr(os, "open", open_then_replace)
    with pytest.raises(ReruncheckError, match="root changed"):
        snapshot(root)


def test_content_race_during_hashing_is_incomplete(tmp_path, monkeypatch):
    import hashlib

    path = tmp_path / "data"
    path.write_bytes(b"original")
    real_sha = hashlib.sha256

    class MutatingHash:
        def __init__(self):
            self.inner = real_sha()

        def update(self, chunk):
            self.inner.update(chunk)
            path.write_bytes(b"changed!")

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(hashlib, "sha256", MutatingHash)
    with pytest.raises(ReruncheckError, match="changed"):
        snapshot(tmp_path)
