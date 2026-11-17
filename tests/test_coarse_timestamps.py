import hashlib
import os

import pytest

from reruncheck.limits import ReruncheckError
from reruncheck.snapshot import snapshot


def test_same_tick_content_change_is_incomplete(tmp_path, monkeypatch):
    path = tmp_path / "data"
    path.write_bytes(b"original")
    initial = path.stat()
    identity = (initial.st_dev, initial.st_ino)
    real_stat, real_fstat, real_sha = os.stat, os.fstat, hashlib.sha256
    mutated = False

    class SameTickStat:
        def __init__(self, info):
            self.info = info
            self.st_mtime_ns = initial.st_mtime_ns
            self.st_ctime_ns = initial.st_ctime_ns

        def __getattr__(self, name):
            return getattr(self.info, name)

    def same_tick(call):
        def observed(*args, **kwargs):
            info = call(*args, **kwargs)
            if (info.st_dev, info.st_ino) == identity:
                return SameTickStat(info)
            return info

        return observed

    class MutatingHash:
        def __init__(self):
            self.inner = real_sha()

        def update(self, chunk):
            nonlocal mutated
            self.inner.update(chunk)
            if not mutated:
                mutated = True
                path.write_bytes(b"changed!")

        def hexdigest(self):
            return self.inner.hexdigest()

    monkeypatch.setattr(os, "stat", same_tick(real_stat))
    monkeypatch.setattr(os, "fstat", same_tick(real_fstat))
    monkeypatch.setattr(hashlib, "sha256", MutatingHash)
    with pytest.raises(ReruncheckError, match="changed"):
        snapshot(tmp_path)
    assert mutated
