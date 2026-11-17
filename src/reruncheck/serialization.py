"""Strict version-one imports; never construct paths from unvalidated JSON."""

import fnmatch
import json
import os
import re
import stat

from .limits import Limits, ReruncheckError
from .snapshot import Entry, Snapshot


def require(condition, message):
    if not condition:
        raise ReruncheckError(message)


def safe_path(value):
    require(type(value) is str and 0 < len(value) <= 4096, "invalid relative path")
    require(
        "\\" not in value
        and "\0" not in value
        and ":" not in value.split("/")[0]
        and all(part not in ("", ".", "..") for part in value.split("/")),
        "unsafe relative path",
    )
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def reject_constant(value):
    raise ReruncheckError("non-finite JSON number: " + value)


def from_dict(doc, *, limits=None):
    limits = limits or Limits()
    require(
        type(doc) is dict
        and set(doc) == {"schema_version", "type", "entries", "coverage", "root_mode"},
        "invalid snapshot envelope",
    )
    require(
        type(doc["schema_version"]) is int
        and doc["schema_version"] == 1
        and doc["type"] == "snapshot",
        "unsupported snapshot version/type",
    )
    require(type(doc["root_mode"]) is int and 0 <= doc["root_mode"] <= 0o7777, "invalid root mode")
    coverage = doc["coverage"]
    require(type(coverage) is dict, "invalid coverage")
    ignores = coverage.get("ignore_patterns")
    excluded = coverage.get("excluded_paths")
    require(
        type(ignores) is list
        and len(ignores) <= 100
        and all(type(p) is str and 0 < len(p) <= 1024 for p in ignores),
        "invalid ignore patterns",
    )
    require(
        type(excluded) is list and len(excluded) <= limits.max_entries, "invalid excluded paths"
    )
    for path in excluded:
        safe_path(path)
        require(
            any(fnmatch.fnmatchcase(path, pattern) for pattern in ignores),
            "excluded path does not match ignore policy",
        )
    require(excluded == sorted(set(excluded)), "excluded paths must be sorted and unique")
    require(
        type(doc["entries"]) is list and len(doc["entries"]) + len(excluded) <= limits.max_entries,
        "invalid entries or max_entries exceeded",
    )
    entries = []
    seen = {}
    total = 0
    for item in doc["entries"]:
        require(type(item) is dict, "invalid entry object")
        path = safe_path(item.get("path"))
        require(path not in seen, "duplicate entry path")
        kind, mode = item.get("kind"), item.get("mode")
        require(type(kind) is str and kind in ("file", "directory", "symlink"), "invalid kind")
        require(type(mode) is int and 0 <= mode <= 0o7777, "invalid mode")
        keys = {"path", "kind", "mode"}
        if kind == "file":
            keys |= {"size", "sha256"}
            size, digest = item.get("size"), item.get("sha256")
            require(type(size) is int and size >= 0, "invalid file size")
            total += size
            require(total <= limits.max_bytes, "max_bytes exceeded on import")
            require(
                type(digest) is str and re.fullmatch("[0-9a-f]{64}", digest) is not None,
                "invalid SHA-256",
            )
        elif kind == "symlink":
            keys.add("target")
            target = item.get("target")
            require(
                type(target) is str and 0 < len(target) <= 4096 and "\0" not in target,
                "invalid symlink target",
            )
        require(set(item) == keys, "unexpected or missing entry fields")
        require(
            not any(fnmatch.fnmatchcase(path, pattern) for pattern in ignores),
            "included path conflicts with ignore policy",
        )
        seen[path] = kind
        entries.append(Entry(**item))
    for path in seen:
        parent = path.rpartition("/")[0]
        while parent:
            require(seen.get(parent) == "directory", "missing or non-directory parent")
            parent = parent.rpartition("/")[0]
    for path in excluded:
        require(path not in seen, "excluded path is also included")
        parent = path.rpartition("/")[0]
        while parent:
            require(seen.get(parent) == "directory", "excluded path has missing parent")
            parent = parent.rpartition("/")[0]
    result = Snapshot(
        tuple(sorted(entries, key=lambda e: e.path)),
        tuple(ignores),
        tuple(excluded),
        doc["root_mode"],
    )
    require(coverage == result.coverage, "unsupported or malformed comparison coverage")
    return result


def load_snapshot(path, *, limits=None):
    limits = limits or Limits()
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    with os.fdopen(fd, "rb") as stream:
        require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), "snapshot input must be regular")
        raw = stream.read(limits.max_json_bytes + 1)
    require(len(raw) <= limits.max_json_bytes, "snapshot JSON exceeds max_json_bytes")
    return from_dict(
        json.loads(raw, object_pairs_hook=unique_object, parse_constant=reject_constant),
        limits=limits,
    )
