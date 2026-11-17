"""Typed, ordered reasons over complete observations."""

from dataclasses import dataclass
from enum import Enum

from .limits import ReruncheckError


class Reason(str, Enum):
    ADDED = "added"
    REMOVED = "removed"
    KIND = "kind"
    CONTENT = "content"
    MODE = "mode"
    TARGET = "target"


@dataclass(frozen=True)
class Change:
    path: str
    reasons: tuple[Reason, ...]

    def to_dict(self):
        return {"path": self.path, "reasons": [reason.value for reason in self.reasons]}


def compare(before, after):
    if before.ignores != after.ignores:
        raise ReruncheckError("cannot compare snapshots with different ignore patterns")
    left = {entry.path: entry for entry in before.entries}
    right = {entry.path: entry for entry in after.entries}
    changes = []
    if before.root_mode != after.root_mode:
        changes.append(Change(".", (Reason.MODE,)))
    for path in sorted(left.keys() | right.keys()):
        reasons = []
        if path not in left:
            reasons.append(Reason.ADDED)
        elif path not in right:
            reasons.append(Reason.REMOVED)
        else:
            a, b = left[path], right[path]
            if a.kind != b.kind:
                reasons.append(Reason.KIND)
            elif a.kind == "file" and (a.size, a.sha256) != (b.size, b.sha256):
                reasons.append(Reason.CONTENT)
            if a.mode != b.mode:
                reasons.append(Reason.MODE)
            if a.kind == b.kind == "symlink" and a.target != b.target:
                reasons.append(Reason.TARGET)
        if reasons:
            changes.append(Change(path, tuple(reasons)))
    return tuple(changes)
