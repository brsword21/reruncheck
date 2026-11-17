"""Deterministic filesystem observations; symlinks are never followed."""

import fnmatch
import hashlib
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

from .limits import Limits, ReruncheckError


@dataclass(frozen=True)
class Entry:
    path: str
    kind: str
    mode: int
    size: int | None = None
    sha256: str | None = None
    target: str | None = None

    def to_dict(self):
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass(frozen=True)
class Snapshot:
    entries: tuple[Entry, ...]
    ignores: tuple[str, ...] = ()
    excluded: tuple[str, ...] = ()
    root_mode: int = 0o755

    @property
    def coverage(self):
        return {
            "compared": ["path", "kind", "mode", "size", "sha256", "symlink_target", "root_mode"],
            "not_compared": [
                "mtime",
                "atime",
                "ctime",
                "uid",
                "gid",
                "ACLs",
                "xattrs",
                "hardlink_identity",
            ],
            "ignore_patterns": list(self.ignores),
            "excluded_paths": list(self.excluded),
            "directory_exclusion": "matching directories exclude their entire subtree",
            "ignore_syntax": "case-sensitive fnmatch over full relative POSIX paths; * matches /",
        }

    def to_dict(self):
        return {
            "schema_version": 1,
            "type": "snapshot",
            "coverage": self.coverage,
            "entries": [entry.to_dict() for entry in self.entries],
            "root_mode": self.root_mode,
        }


def load_snapshot(path, *, limits=None):
    from .serialization import load_snapshot as load

    return load(path, limits=limits)


def fingerprint(info):
    return (
        info.st_dev,
        info.st_ino,
        info.st_mode,
        info.st_size,
        info.st_mtime_ns,
        info.st_ctime_ns,
    )


def snapshot(root, *, ignores=(), limits=None):
    from .serialization import safe_path

    limits = limits or Limits()
    ignores = tuple(ignores)
    if len(ignores) > 100 or any(type(p) is not str or not p or len(p) > 1024 for p in ignores):
        raise ReruncheckError("ignore patterns must be 1..1024 characters; at most 100")
    root = Path(root)
    entries, excluded = [], []
    total_bytes = 0
    visited = 0

    def walk(fd, prefix=""):
        nonlocal total_bytes, visited
        before = os.fstat(fd)
        names = []
        with os.scandir(fd) as scan:
            for item in scan:
                visited += 1
                if visited > limits.max_entries:
                    raise ReruncheckError("max_entries exceeded (including excluded entries)")
                names.append(item.name)
        for name in sorted(names):
            rel = safe_path(prefix + name)
            if any(fnmatch.fnmatchcase(rel, pattern) for pattern in ignores):
                excluded.append(rel)
                continue
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            mode = stat.S_IMODE(info.st_mode)
            if stat.S_ISLNK(info.st_mode):
                entries.append(Entry(rel, "symlink", mode, target=os.readlink(name, dir_fd=fd)))
            elif stat.S_ISDIR(info.st_mode):
                entries.append(Entry(rel, "directory", mode))
                child = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                try:
                    if fingerprint(info) != fingerprint(os.fstat(child)):
                        raise ReruncheckError("directory changed during traversal")
                    walk(child, rel + "/")
                finally:
                    os.close(child)
            elif stat.S_ISREG(info.st_mode):
                if total_bytes + info.st_size > limits.max_bytes:
                    raise ReruncheckError("max_bytes exceeded")
                digest = hashlib.sha256()
                file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd)
                with os.fdopen(file_fd, "rb", buffering=0) as stream:
                    if fingerprint(info) != fingerprint(os.fstat(stream.fileno())):
                        raise ReruncheckError("file changed before hashing")
                    size = 0
                    while chunk := stream.read(min(65536, limits.max_bytes - total_bytes + 1)):
                        total_bytes += len(chunk)
                        size += len(chunk)
                        if total_bytes > limits.max_bytes:
                            raise ReruncheckError("max_bytes exceeded while hashing")
                        digest.update(chunk)
                    if size != info.st_size or fingerprint(info) != fingerprint(
                        os.fstat(stream.fileno())
                    ):
                        raise ReruncheckError("file changed during hashing")
                    # Same-tick writes can preserve every metadata field. Re-read
                    # without a userspace buffer to validate the observed content.
                    observed_digest = digest.hexdigest()
                    stream.seek(0)
                    verification, verified_size = hashlib.sha256(), 0
                    while chunk := stream.read(min(65536, size - verified_size + 1)):
                        verified_size += len(chunk)
                        if verified_size > size:
                            raise ReruncheckError("file changed during hash verification")
                        verification.update(chunk)
                    if (
                        verified_size != size
                        or verification.hexdigest() != observed_digest
                        or fingerprint(info) != fingerprint(os.fstat(stream.fileno()))
                    ):
                        raise ReruncheckError("file changed during hash verification")
                entries.append(Entry(rel, "file", mode, size, observed_digest))
            else:
                raise ReruncheckError(f"unsupported file type: {rel}")
            if fingerprint(info) != fingerprint(os.stat(name, dir_fd=fd, follow_symlinks=False)):
                raise ReruncheckError(f"entry changed during traversal: {rel}")
        if fingerprint(before) != fingerprint(os.fstat(fd)):
            raise ReruncheckError("directory changed during traversal")

    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        root_mode = stat.S_IMODE(os.fstat(fd).st_mode)
        walk(fd)
        if fingerprint(os.stat(root, follow_symlinks=False)) != fingerprint(os.fstat(fd)):
            raise ReruncheckError("root changed during traversal")
    finally:
        os.close(fd)
    return Snapshot(
        tuple(sorted(entries, key=lambda entry: entry.path)),
        ignores,
        tuple(sorted(excluded)),
        root_mode,
    )
