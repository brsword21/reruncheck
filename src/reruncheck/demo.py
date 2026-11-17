"""Offline authored examples loaded from installed package resources."""

import sys
import tempfile
from importlib.resources import as_file, files
from pathlib import Path

from .limits import ReruncheckError
from .runner import check


def demo(case="stable", *, limits=None):
    if case not in ("stable", "broken"):
        raise ReruncheckError("demo case must be stable or broken")
    with tempfile.TemporaryDirectory(prefix="reruncheck-demo-") as temporary:
        fixture, expected = Path(temporary) / "input", Path(temporary) / "expected"
        fixture.mkdir()
        expected.mkdir()
        (fixture / "data.txt").write_bytes(b"value=one\r\n\r\n")
        (expected / "data.txt").write_bytes(b"value=one\n" if case == "stable" else b"value=one!\n")
        resource = files("reruncheck").joinpath("resources", "normalizer.py")
        with as_file(resource) as script:
            return check(
                fixture,
                [sys.executable, str(script), case],
                trust_command=True,
                expect=expected,
                limits=limits,
            )
