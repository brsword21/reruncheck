"""Finite original trees; the oracle uses raw model bytes, never snapshot digests."""

import copy
import random
import stat
from collections import Counter

import pytest

from reruncheck.diff import compare
from reruncheck.snapshot import snapshot

OPERATIONS = ("equal", "add", "remove", "content", "mode", "type", "target", "rename")


def materialize(root, model):
    root.mkdir()
    for name, node in sorted(model.items()):
        kind, mode, payload = node
        path = root / name
        if kind == "directory":
            path.mkdir()
        elif kind == "file":
            path.write_bytes(payload)
        else:
            path.symlink_to(payload)
        if kind != "symlink":
            path.chmod(mode)
        else:
            # Link permissions are platform-defined; record creation mode in the model.
            model[name] = (kind, stat.S_IMODE(path.lstat().st_mode), payload)


def oracle(left, right):
    expected = []
    for path in sorted(set(left) | set(right)):
        reasons = []
        if path not in left:
            reasons = ["added"]
        elif path not in right:
            reasons = ["removed"]
        else:
            a, b = left[path], right[path]
            if a[0] != b[0]:
                reasons.append("kind")
            elif a[0] == "file" and a[2] != b[2]:
                reasons.append("content")
            if a[1] != b[1]:
                reasons.append("mode")
            if a[0] == b[0] == "symlink" and a[2] != b[2]:
                reasons.append("target")
        if reasons:
            expected.append({"path": path, "reasons": reasons})
    return expected


@pytest.mark.parametrize("seed", range(8))
def test_deterministic_mutation_simulations_against_raw_tree_oracle(tmp_path, seed):
    randomizer = random.Random(20261117 + seed)
    counts = Counter()
    reasons_seen = Counter()
    for trial in range(24):
        before = {
            ".hidden": ("file", 0o600, b"hidden"),
            "empty": ("directory", 0o755, None),
            "nested": ("directory", 0o755, None),
            "nested/data": ("file", 0o644, randomizer.randbytes(16)),
            "link": ("symlink", 0o777, "nested/data"),
        }
        for index in range(4):
            before[f"f{index}"] = (
                "file",
                randomizer.choice([0o600, 0o644, 0o755]),
                randomizer.randbytes(randomizer.randrange(40)),
            )
        after = copy.deepcopy(before)
        operation = OPERATIONS[trial % len(OPERATIONS)]
        victim = f"f{randomizer.randrange(4)}"
        if operation == "add":
            after["added"] = ("directory", 0o700, None)
        elif operation == "remove":
            del after[victim]
        elif operation == "content":
            kind, mode, payload = after[victim]
            after[victim] = (kind, mode, payload + b"!")
        elif operation == "mode":
            kind, mode, payload = after[victim]
            after[victim] = (kind, 0o700 if mode != 0o700 else 0o755, payload)
        elif operation == "type":
            after[victim] = ("directory", 0o755, None)
        elif operation == "target":
            after["link"] = ("symlink", 0o777, ".hidden")
        elif operation == "rename":
            after["renamed"] = after.pop(victim)
        a, b = tmp_path / f"{trial}-a", tmp_path / f"{trial}-b"
        materialize(a, before)
        materialize(b, after)
        actual = [change.to_dict() for change in compare(snapshot(a), snapshot(b))]
        expected = oracle(before, after)
        assert actual == expected, (seed, trial, operation)
        counts[operation] += 1
        reasons_seen.update(reason for change in actual for reason in change["reasons"])
    assert counts == dict.fromkeys(OPERATIONS, 3)
    assert set(reasons_seen) == {"added", "removed", "content", "mode", "kind", "target"}
    print(
        f"seed={20261117 + seed} tree_pairs={sum(counts.values())} "
        f"operations={dict(counts)} observed_reasons={dict(sorted(reasons_seen.items()))}"
    )
