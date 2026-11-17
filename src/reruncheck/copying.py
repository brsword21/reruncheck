"""Bounded inventory-based copying without dereferencing source links."""

import hashlib
import os
import stat
from collections import deque

from .limits import ReruncheckError
from .snapshot import fingerprint


def validate_links(state):
    """Resolve the copied link graph virtually, rejecting every escape, not only endpoints."""
    links = {entry.path: entry.target for entry in state.entries if entry.kind == "symlink"}
    if any(os.path.isabs(target) for target in links.values()):
        raise ReruncheckError("absolute source symlinks are not supported for execution")
    for path, target in links.items():
        parent = path.split("/")[:-1]
        pending = deque(parent + target.split("/"))
        resolved = []
        hops = steps = 0
        while pending:
            steps += 1
            if steps > 8192:
                raise ReruncheckError("source symlink resolution budget exceeded")
            part = pending.popleft()
            if part in ("", "."):
                continue
            if part == "..":
                if not resolved:
                    raise ReruncheckError("source symlink escapes disposable fixture")
                resolved.pop()
                continue
            resolved.append(part)
            candidate = "/".join(resolved)
            if candidate in links:
                hops += 1
                if hops > 40:
                    raise ReruncheckError("source symlink cycle or excessive link chain")
                resolved.pop()
                pending.extendleft(reversed(links[candidate].split("/")))


def parent_fd(root_fd, relative):
    parts = relative.split("/")
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            os.close(fd)
            fd = child
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def copy_fixture(source, destination, state, limits):
    destination.mkdir(mode=0o700)
    root_fd = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    total = 0
    try:
        for entry in state.entries:
            target = destination / entry.path
            if entry.kind == "directory":
                target.mkdir(mode=0o700)
                continue
            parent, name = parent_fd(root_fd, entry.path)
            try:
                if entry.kind == "symlink":
                    if os.readlink(name, dir_fd=parent) != entry.target:
                        raise ReruncheckError("source symlink changed during copy")
                    target.symlink_to(entry.target)
                    # macOS records link permissions; Linux links have fixed permissions.
                    if os.lstat(target).st_mode & 0o7777 != entry.mode:
                        os.chmod(target, entry.mode, follow_symlinks=False)
                else:
                    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                    digest, size = hashlib.sha256(), 0
                    with os.fdopen(fd, "rb") as incoming, target.open("xb") as outgoing:
                        before = os.fstat(incoming.fileno())
                        if not stat.S_ISREG(before.st_mode):
                            raise ReruncheckError("source file type changed during copy")
                        while chunk := incoming.read(min(65536, limits.max_bytes - total + 1)):
                            total += len(chunk)
                            size += len(chunk)
                            if total > limits.max_bytes:
                                raise ReruncheckError("max_bytes exceeded while copying")
                            digest.update(chunk)
                            outgoing.write(chunk)
                        if (
                            fingerprint(before) != fingerprint(os.fstat(incoming.fileno()))
                            or size != entry.size
                            or digest.hexdigest() != entry.sha256
                            or stat.S_IMODE(before.st_mode) != entry.mode
                        ):
                            raise ReruncheckError("source file changed during copy")
                    target.chmod(entry.mode)
            finally:
                os.close(parent)
        for entry in reversed(state.entries):
            if entry.kind == "directory":
                (destination / entry.path).chmod(entry.mode)
        destination.chmod(state.root_mode)
    finally:
        os.close(root_fd)
